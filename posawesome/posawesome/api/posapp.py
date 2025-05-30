# -*- coding: utf-8 -*-
# Copyright (c) 2020, Youssef Restom and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe.utils import nowdate, flt, cstr, getdate, cint, money_in_words
from erpnext.setup.utils import get_exchange_rate
from frappe import _
from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
from erpnext.stock.get_item_details import get_item_details
from erpnext.accounts.doctype.pos_profile.pos_profile import get_item_groups
from frappe.utils.background_jobs import enqueue
from erpnext.accounts.party import get_party_bank_account
from erpnext.stock.doctype.batch.batch import (
    get_batch_no,
    get_batch_qty,
)
from erpnext.accounts.doctype.payment_request.payment_request import (
    get_dummy_message,
    get_existing_payment_request_amount,
)

from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
    get_loyalty_program_details_with_points,
)
from posawesome.posawesome.doctype.pos_coupon.pos_coupon import check_coupon_code
from posawesome.posawesome.doctype.delivery_charges.delivery_charges import (
    get_applicable_delivery_charges as _get_applicable_delivery_charges,
)
from frappe.utils.caching import redis_cache
from typing import List, Dict


@frappe.whitelist()
def get_opening_dialog_data():
    data = {}
    data["companies"] = frappe.get_list("Company", limit_page_length=0, order_by="name")
    data["pos_profiles_data"] = frappe.get_list(
        "POS Profile",
        filters={"disabled": 0},
        fields=["name", "company", "currency"],
        limit_page_length=0,
        order_by="name",
    )

    pos_profiles_list = []
    for i in data["pos_profiles_data"]:
        pos_profiles_list.append(i.name)

    payment_method_table = (
        "POS Payment Method" if get_version() == 13 else "Sales Invoice Payment"
    )
    data["payments_method"] = frappe.get_list(
        payment_method_table,
        filters={"parent": ["in", pos_profiles_list]},
        fields=["*"],
        limit_page_length=0,
        order_by="parent",
        ignore_permissions=True,
    )
    # set currency from pos profile
    for mode in data["payments_method"]:
        mode["currency"] = frappe.get_cached_value(
            "POS Profile", mode["parent"], "currency"
        )

    return data


@frappe.whitelist()
def create_opening_voucher(pos_profile, company, balance_details):
    balance_details = json.loads(balance_details)

    new_pos_opening = frappe.get_doc(
        {
            "doctype": "POS Opening Shift",
            "period_start_date": frappe.utils.get_datetime(),
            "posting_date": frappe.utils.getdate(),
            "user": frappe.session.user,
            "pos_profile": pos_profile,
            "company": company,
            "docstatus": 1,
        }
    )
    new_pos_opening.set("balance_details", balance_details)
    new_pos_opening.insert(ignore_permissions=True)

    data = {}
    data["pos_opening_shift"] = new_pos_opening.as_dict()
    update_opening_shift_data(data, new_pos_opening.pos_profile)
    return data


@frappe.whitelist()
def check_opening_shift(user):
    open_vouchers = frappe.db.get_all(
        "POS Opening Shift",
        filters={
            "user": user,
            "pos_closing_shift": ["in", ["", None]],
            "docstatus": 1,
            "status": "Open",
        },
        fields=["name", "pos_profile"],
        order_by="period_start_date desc",
    )
    data = ""
    if len(open_vouchers) > 0:
        data = {}
        data["pos_opening_shift"] = frappe.get_doc(
            "POS Opening Shift", open_vouchers[0]["name"]
        )
        update_opening_shift_data(data, open_vouchers[0]["pos_profile"])
    return data


def update_opening_shift_data(data, pos_profile):
    data["pos_profile"] = frappe.get_doc("POS Profile", pos_profile)
    data["company"] = frappe.get_doc("Company", data["pos_profile"].company)
    allow_negative_stock = frappe.get_value(
        "Stock Settings", None, "allow_negative_stock"
    )
    data["stock_settings"] = {}
    data["stock_settings"].update({"allow_negative_stock": allow_negative_stock})


@frappe.whitelist()
def get_items(
    pos_profile, price_list=None, item_group="", search_value="", customer=None
):
    _pos_profile = json.loads(pos_profile)
    use_price_list = _pos_profile.get("posa_use_server_cache")

    @redis_cache(ttl=60)
    def __get_items(pos_profile, price_list, item_group, search_value, customer=None):
        return _get_items(pos_profile, price_list, item_group, search_value, customer)

    def _get_items(pos_profile, price_list, item_group, search_value, customer=None):
        pos_profile = json.loads(pos_profile)
        condition = ""
        
        # Clear quantity cache to ensure fresh values on each search
        try:
            if hasattr(frappe.local.cache, "delete_key"):
                frappe.local.cache.delete_key('bin_qty_cache')
            elif frappe.cache().get_value('bin_qty_cache'):
                frappe.cache().delete_value('bin_qty_cache')
        except Exception as e:
            frappe.log_error(f"Error clearing bin_qty_cache: {str(e)}", "POS Awesome")
        
        today = nowdate()
        warehouse = pos_profile.get("warehouse")
        use_limit_search = pos_profile.get("pose_use_limit_search")
        search_serial_no = pos_profile.get("posa_search_serial_no")
        search_batch_no = pos_profile.get("posa_search_batch_no")
        posa_show_template_items = pos_profile.get("posa_show_template_items")
        posa_display_items_in_stock = pos_profile.get("posa_display_items_in_stock")
        search_limit = 0

        if not price_list:
            price_list = pos_profile.get("selling_price_list")

        limit = ""

        condition += get_item_group_condition(pos_profile.get("name"))

        if use_limit_search:
            search_limit = pos_profile.get("posa_search_limit") or 500
            data = {}
            if search_value:
                data = search_serial_or_batch_or_barcode_number(
                    search_value, search_serial_no
                )

            item_code = data.get("item_code") if data.get("item_code") else search_value
            serial_no = data.get("serial_no") if data.get("serial_no") else ""
            batch_no = data.get("batch_no") if data.get("batch_no") else ""
            barcode = data.get("barcode") if data.get("barcode") else ""

            condition += get_seearch_items_conditions(
                item_code, serial_no, batch_no, barcode
            )
            if item_group:
                condition += " AND item_group like '%{item_group}%'".format(
                    item_group=item_group
                )
            limit = " LIMIT {search_limit}".format(search_limit=search_limit)

        if not posa_show_template_items:
            condition += " AND has_variants = 0"

        result = []

        items_data = frappe.db.sql(
            """
            SELECT
                name AS item_code,
                item_name,
                description,
                stock_uom,
                image,
                is_stock_item,
                has_variants,
                variant_of,
                item_group,
                idx as idx,
                has_batch_no,
                has_serial_no,
                max_discount,
                brand
            FROM
                `tabItem`
            WHERE
                disabled = 0
                    AND is_sales_item = 1
                    AND is_fixed_asset = 0
                    {condition}
            ORDER BY
                item_name asc
            {limit}
                """.format(
                condition=condition, limit=limit
            ),
            as_dict=1,
        )

        if items_data:
            items = [d.item_code for d in items_data]
            item_prices_data = frappe.get_all(
                "Item Price",
                fields=["item_code", "price_list_rate", "currency", "uom"],
                filters={
                    "price_list": price_list,
                    "item_code": ["in", items],
                    "currency": pos_profile.get("currency"),
                    "selling": 1,
                    "valid_from": ["<=", today],
                    "customer": ["in", ["", None, customer]],
                },
                or_filters=[
                    ["valid_upto", ">=", today],
                    ["valid_upto", "in", ["", None]],
                ],
                order_by="valid_from ASC, valid_upto DESC",
            )

            item_prices = {}
            for d in item_prices_data:
                item_prices.setdefault(d.item_code, {})
                item_prices[d.item_code][d.get("uom") or "None"] = d

            for item in items_data:
                item_code = item.item_code
                item_price = {}
                if item_prices.get(item_code):
                    item_price = (
                        item_prices.get(item_code).get(item.stock_uom)
                        or item_prices.get(item_code).get("None")
                        or {}
                    )
                item_barcode = frappe.get_all(
                    "Item Barcode",
                    filters={"parent": item_code},
                    fields=["barcode", "posa_uom"],
                )
                batch_no_data = []
                if search_batch_no:
                    batch_list = get_batch_qty(warehouse=warehouse, item_code=item_code)
                    if batch_list:
                        for batch in batch_list:
                            if batch.qty > 0 and batch.batch_no:
                                batch_doc = frappe.get_cached_doc(
                                    "Batch", batch.batch_no
                                )
                                if (
                                    str(batch_doc.expiry_date) > str(today)
                                    or batch_doc.expiry_date in ["", None]
                                ) and batch_doc.disabled == 0:
                                    batch_no_data.append(
                                        {
                                            "batch_no": batch.batch_no,
                                            "batch_qty": batch.qty,
                                            "expiry_date": batch_doc.expiry_date,
                                            "batch_price": batch_doc.posa_batch_price,
                                            "manufacturing_date": batch_doc.manufacturing_date,
                                        }
                                    )
                serial_no_data = []
                if search_serial_no:
                    serial_no_data = frappe.get_all(
                        "Serial No",
                        filters={
                            "item_code": item_code,
                            "status": "Active",
                            "warehouse": warehouse,
                        },
                        fields=["name as serial_no"],
                    )
                item_stock_qty = 0
                if pos_profile.get("posa_display_items_in_stock") or use_limit_search:
                    item_stock_qty = get_stock_availability(
                        item_code, pos_profile.get("warehouse")
                    )
                attributes = ""
                if pos_profile.get("posa_show_template_items") and item.has_variants:
                    attributes = get_item_attributes(item.item_code)
                item_attributes = ""
                if pos_profile.get("posa_show_template_items") and item.variant_of:
                    item_attributes = frappe.get_all(
                        "Item Variant Attribute",
                        fields=["attribute", "attribute_value"],
                        filters={"parent": item.item_code, "parentfield": "attributes"},
                    )
                if posa_display_items_in_stock and (
                    not item_stock_qty or item_stock_qty < 0
                ):
                    pass
                else:
                    row = {}
                    row.update(item)
                    row.update(
                        {
                            "rate": item_price.get("price_list_rate") or 0,
                            "currency": item_price.get("currency")
                            or pos_profile.get("currency"),
                            "item_barcode": item_barcode or [],
                            "actual_qty": item_stock_qty or 0,
                            "serial_no_data": serial_no_data or [],
                            "batch_no_data": batch_no_data or [],
                            "attributes": attributes or "",
                            "item_attributes": item_attributes or "",
                        }
                    )
                    result.append(row)
        return result

    if use_price_list:
        return __get_items(pos_profile, price_list, item_group, search_value, customer)
    else:
        return _get_items(pos_profile, price_list, item_group, search_value, customer)


def get_item_group_condition(pos_profile):
    cond = " and 1=1"
    item_groups = get_item_groups(pos_profile)
    if item_groups:
        cond = " and item_group in (%s)" % (", ".join(["%s"] * len(item_groups)))

    return cond % tuple(item_groups)


def get_root_of(doctype):
    """Get root element of a DocType with a tree structure"""
    result = frappe.db.sql(
        """select t1.name from `tab{0}` t1 where
		(select count(*) from `tab{1}` t2 where
			t2.lft < t1.lft and t2.rgt > t1.rgt) = 0
		and t1.rgt > t1.lft""".format(
            doctype, doctype
        )
    )
    return result[0][0] if result else None


@frappe.whitelist()
def get_items_groups():
    return frappe.db.sql(
        """
        select name 
        from `tabItem Group`
        where is_group = 0
        order by name
        LIMIT 0, 200 """,
        as_dict=1,
    )


def get_customer_groups(pos_profile):
    customer_groups = []
    if pos_profile.get("customer_groups"):
        # Get items based on the item groups defined in the POS profile
        for data in pos_profile.get("customer_groups"):
            customer_groups.extend(
                [
                    "%s" % frappe.db.escape(d.get("name"))
                    for d in get_child_nodes(
                        "Customer Group", data.get("customer_group")
                    )
                ]
            )

    return list(set(customer_groups))


def get_child_nodes(group_type, root):
    lft, rgt = frappe.db.get_value(group_type, root, ["lft", "rgt"])
    return frappe.db.sql(
        """ Select name, lft, rgt from `tab{tab}` where
			lft >= {lft} and rgt <= {rgt} order by lft""".format(
            tab=group_type, lft=lft, rgt=rgt
        ),
        as_dict=1,
    )


def get_customer_group_condition(pos_profile):
    cond = "disabled = 0"
    customer_groups = get_customer_groups(pos_profile)
    if customer_groups:
        cond = " customer_group in (%s)" % (", ".join(["%s"] * len(customer_groups)))

    return cond % tuple(customer_groups)


@frappe.whitelist()
def get_customer_names(pos_profile):
    _pos_profile = json.loads(pos_profile)
    ttl = _pos_profile.get("posa_server_cache_duration")
    if ttl:
        ttl = int(ttl) * 60

    @redis_cache(ttl=ttl or 1800)
    def __get_customer_names(pos_profile):
        return _get_customer_names(pos_profile)

    def _get_customer_names(pos_profile):
        pos_profile = json.loads(pos_profile)
        condition = ""
        condition += get_customer_group_condition(pos_profile)
        customers = frappe.db.sql(
            """
            SELECT name, mobile_no, email_id, tax_id, customer_name, primary_address
            FROM `tabCustomer`
            WHERE {0}
            ORDER by name
            """.format(
                condition
            ),
            as_dict=1,
        )
        return customers

    if _pos_profile.get("posa_use_server_cache"):
        return __get_customer_names(pos_profile)
    else:
        return _get_customer_names(pos_profile)


@frappe.whitelist()
def get_sales_person_names():
    import json
    print("Fetching sales persons...")
    try:
        sales_persons = frappe.get_list(
            "Sales Person",
            filters={"enabled": 1},
            fields=["name", "sales_person_name"],
            limit_page_length=100000,
        )
        print(f"Found {len(sales_persons)} sales persons: {json.dumps(sales_persons)}")
        return sales_persons
    except Exception as e:
        print(f"Error fetching sales persons: {str(e)}")
        frappe.log_error(f"Error fetching sales persons: {str(e)}", "POS Sales Person Error")
        return []


def add_taxes_from_tax_template(item, parent_doc):
    accounts_settings = frappe.get_cached_doc("Accounts Settings")
    add_taxes_from_item_tax_template = (
        accounts_settings.add_taxes_from_item_tax_template
    )
    if item.get("item_tax_template") and add_taxes_from_item_tax_template:
        item_tax_template = item.get("item_tax_template")
        taxes_template_details = frappe.get_all(
            "Item Tax Template Detail",
            filters={"parent": item_tax_template},
            fields=["tax_type"],
        )

        for tax_detail in taxes_template_details:
            tax_type = tax_detail.get("tax_type")

            found = any(tax.account_head == tax_type for tax in parent_doc.taxes)
            if not found:
                tax_row = parent_doc.append("taxes", {})
                tax_row.update(
                    {
                        "description": str(tax_type).split(" - ")[0],
                        "charge_type": "On Net Total",
                        "account_head": tax_type,
                    }
                )

                if parent_doc.doctype == "Purchase Order":
                    tax_row.update({"category": "Total", "add_deduct_tax": "Add"})
                tax_row.db_insert()

def validate_return_items(original_invoice_name, return_items):
    """
    Ensure that return items do not exceed the quantity from the original invoice.
    """
    original_invoice = frappe.get_doc("Sales Invoice", original_invoice_name)
    original_item_qty = {}

    for item in original_invoice.items:
        original_item_qty[item.item_code] = original_item_qty.get(item.item_code, 0) + item.qty

    returned_items = frappe.get_all(
        "Sales Invoice",
        filters={
            "return_against": original_invoice_name,
            "docstatus": 1,
            "is_return": 1
        },
        fields=["name"]
    )

    for returned_invoice in returned_items:
        ret_doc = frappe.get_doc("Sales Invoice", returned_invoice.name)
        for item in ret_doc.items:
            if item.item_code in original_item_qty:
                original_item_qty[item.item_code] -= abs(item.qty)

    for item in return_items:
        item_code = item.get("item_code")
        return_qty = abs(item.get("qty", 0))
        if item_code in original_item_qty and return_qty > original_item_qty[item_code]:
            return {
                "valid": False,
                "message": _("You are trying to return more quantity for item {0} than was sold.").format(item_code),
            }

    return {"valid": True}
    
@frappe.whitelist()
def update_invoice(data):
    data = json.loads(data)
    if data.get("name"):
        invoice_doc = frappe.get_doc("Sales Invoice", data.get("name"))
        invoice_doc.update(data)
    else:
        invoice_doc = frappe.get_doc(data)

    # Set currency from data before set_missing_values
    selected_currency = data.get("currency")
    
    # Set missing values first
    invoice_doc.set_missing_values()
    
    # Ensure selected currency is preserved after set_missing_values
    if selected_currency:
        invoice_doc.currency = selected_currency
        # Get default conversion rate from ERPNext if currency is different from company currency
        if invoice_doc.currency != frappe.get_cached_value("Company", invoice_doc.company, "default_currency"):
            company_currency = frappe.get_cached_value("Company", invoice_doc.company, "default_currency")
            # Get exchange rate from selected currency to base currency
            exchange_rate = get_exchange_rate(
                invoice_doc.currency,
                company_currency,
                invoice_doc.posting_date
            )
            invoice_doc.conversion_rate = exchange_rate
            invoice_doc.plc_conversion_rate = exchange_rate
            invoice_doc.price_list_currency = selected_currency

            # Update rates and amounts for all items using multiplication
            for item in invoice_doc.items:
                if item.price_list_rate:
                    # If exchange rate is 285 PKR = 1 USD
                    # To convert USD to PKR: multiply by exchange rate
                    # Example: 0.35 USD * 285 = 100 PKR
                    item.base_price_list_rate = flt(item.price_list_rate * exchange_rate, item.precision("base_price_list_rate"))
                if item.rate:
                    item.base_rate = flt(item.rate * exchange_rate, item.precision("base_rate"))
                if item.amount:
                    item.base_amount = flt(item.amount * exchange_rate, item.precision("base_amount"))

            # Update payment amounts
            for payment in invoice_doc.payments:
                payment.base_amount = flt(payment.amount * exchange_rate, payment.precision("base_amount"))

            # Update invoice level amounts
            invoice_doc.base_total = flt(invoice_doc.total * exchange_rate, invoice_doc.precision("base_total"))
            invoice_doc.base_net_total = flt(invoice_doc.net_total * exchange_rate, invoice_doc.precision("base_net_total"))
            invoice_doc.base_grand_total = flt(invoice_doc.grand_total * exchange_rate, invoice_doc.precision("base_grand_total"))
            invoice_doc.base_rounded_total = flt(invoice_doc.rounded_total * exchange_rate, invoice_doc.precision("base_rounded_total"))
            invoice_doc.base_in_words = money_in_words(invoice_doc.base_rounded_total, invoice_doc.company_currency)

            # Update data to be sent back to frontend
            data["conversion_rate"] = exchange_rate
            data["plc_conversion_rate"] = exchange_rate

    invoice_doc.flags.ignore_permissions = True
    frappe.flags.ignore_account_permission = True
    invoice_doc.docstatus = 0
    invoice_doc.save()

    # Return both the invoice doc and the updated data
    response = invoice_doc.as_dict()
    response["conversion_rate"] = invoice_doc.conversion_rate
    response["plc_conversion_rate"] = invoice_doc.conversion_rate
    return response


@frappe.whitelist()
def submit_invoice(invoice, data):
    data = json.loads(data)
    invoice = json.loads(invoice)
    invoice_doc = frappe.get_doc("Sales Invoice", invoice.get("name"))
    invoice_doc.update(invoice)
    if invoice.get("posa_delivery_date"):
        invoice_doc.update_stock = 0
    mop_cash_list = [
        i.mode_of_payment
        for i in invoice_doc.payments
        if "cash" in i.mode_of_payment.lower() and i.type == "Cash"
    ]
    if len(mop_cash_list) > 0:
        cash_account = get_bank_cash_account(mop_cash_list[0], invoice_doc.company)
    else:
        cash_account = {
            "account": frappe.get_value(
                "Company", invoice_doc.company, "default_cash_account"
            )
        }

    # Update remarks with items details
    items = []
    for item in invoice_doc.items:
        if item.item_name and item.rate and item.qty:
            total = item.rate * item.qty
            items.append(f"{item.item_name} - Rate: {item.rate}, Qty: {item.qty}, Amount: {total}")
    
    # Add the grand total at the end of remarks
    grand_total = f"\nGrand Total: {invoice_doc.grand_total}"
    items.append(grand_total)
    
    invoice_doc.remarks = "\n".join(items)

    # creating advance payment
    if data.get("credit_change"):
        advance_payment_entry = frappe.get_doc(
            {
                "doctype": "Payment Entry",
                "mode_of_payment": "Cash",
                "paid_to": cash_account["account"],
                "payment_type": "Receive",
                "party_type": "Customer",
                "party": invoice_doc.get("customer"),
                "paid_amount": invoice_doc.get("credit_change"),
                "received_amount": invoice_doc.get("credit_change"),
                "company": invoice_doc.get("company"),
            }
        )

        advance_payment_entry.flags.ignore_permissions = True
        frappe.flags.ignore_account_permission = True
        advance_payment_entry.save()
        advance_payment_entry.submit()

    # calculating cash
    total_cash = 0
    if data.get("redeemed_customer_credit"):
        total_cash = invoice_doc.total - float(data.get("redeemed_customer_credit"))

    is_payment_entry = 0
    if data.get("redeemed_customer_credit"):
        for row in data.get("customer_credit_dict"):
            if row["type"] == "Advance" and row["credit_to_redeem"]:
                advance = frappe.get_doc("Payment Entry", row["credit_origin"])

                advance_payment = {
                    "reference_type": "Payment Entry",
                    "reference_name": advance.name,
                    "remarks": advance.remarks,
                    "advance_amount": advance.unallocated_amount,
                    "allocated_amount": row["credit_to_redeem"],
                }

                invoice_doc.append("advances", advance_payment)
                invoice_doc.is_pos = 0
                is_payment_entry = 1

    payments = invoice_doc.payments

    # if frappe.get_value("POS Profile", invoice_doc.pos_profile, "posa_auto_set_batch"):
    #     set_batch_nos(invoice_doc, "warehouse", throw=True)
    set_batch_nos_for_bundels(invoice_doc, "warehouse", throw=True)

    invoice_doc.flags.ignore_permissions = True
    frappe.flags.ignore_account_permission = True
    invoice_doc.posa_is_printed = 1
    invoice_doc.save()

    if data.get("due_date"):
        frappe.db.set_value(
            "Sales Invoice",
            invoice_doc.name,
            "due_date",
            data.get("due_date"),
            update_modified=False,
        )

    if frappe.get_value(
        "POS Profile",
        invoice_doc.pos_profile,
        "posa_allow_submissions_in_background_job",
    ):
        invoices_list = frappe.get_all(
            "Sales Invoice",
            filters={
                "posa_pos_opening_shift": invoice_doc.posa_pos_opening_shift,
                "docstatus": 0,
                "posa_is_printed": 1,
            },
        )
        for invoice in invoices_list:
            enqueue(
                method=submit_in_background_job,
                queue="short",
                timeout=1000,
                is_async=True,
                kwargs={
                    "invoice": invoice.name,
                    "data": data,
                    "is_payment_entry": is_payment_entry,
                    "total_cash": total_cash,
                    "cash_account": cash_account,
                    "payments": payments,
                },
            )
    else:
        invoice_doc.submit()
        redeeming_customer_credit(
            invoice_doc, data, is_payment_entry, total_cash, cash_account, payments
        )

    return {"name": invoice_doc.name, "status": invoice_doc.docstatus}


def set_batch_nos_for_bundels(doc, warehouse_field, throw=False):
    """Automatically select `batch_no` for outgoing items in item table"""
    for d in doc.packed_items:
        qty = d.get("stock_qty") or d.get("transfer_qty") or d.get("qty") or 0
        has_batch_no = frappe.db.get_value("Item", d.item_code, "has_batch_no")
        warehouse = d.get(warehouse_field, None)
        if has_batch_no and warehouse and qty > 0:
            if not d.batch_no:
                d.batch_no = get_batch_no(
                    d.item_code, warehouse, qty, throw, d.serial_no
                )
            else:
                batch_qty = get_batch_qty(batch_no=d.batch_no, warehouse=warehouse)
                if flt(batch_qty, d.precision("qty")) < flt(qty, d.precision("qty")):
                    frappe.throw(
                        _(
                            "Row #{0}: The batch {1} has only {2} qty. Please select another batch which has {3} qty available or split the row into multiple rows, to deliver/issue from multiple batches"
                        ).format(d.idx, d.batch_no, batch_qty, qty)
                    )


def redeeming_customer_credit(
    invoice_doc, data, is_payment_entry, total_cash, cash_account, payments
):
    # redeeming customer credit with journal voucher
    today = nowdate()
    if data.get("redeemed_customer_credit"):
        cost_center = frappe.get_value(
            "POS Profile", invoice_doc.pos_profile, "cost_center"
        )
        if not cost_center:
            cost_center = frappe.get_value(
                "Company", invoice_doc.company, "cost_center"
            )
        if not cost_center:
            frappe.throw(
                _("Cost Center is not set in pos profile {}").format(
                    invoice_doc.pos_profile
                )
            )
        for row in data.get("customer_credit_dict"):
            if row["type"] == "Invoice" and row["credit_to_redeem"]:
                outstanding_invoice = frappe.get_doc(
                    "Sales Invoice", row["credit_origin"]
                )

                jv_doc = frappe.get_doc(
                    {
                        "doctype": "Journal Entry",
                        "voucher_type": "Journal Entry",
                        "posting_date": today,
                        "company": invoice_doc.company,
                    }
                )

                jv_debit_entry = {
                    "account": outstanding_invoice.debit_to,
                    "party_type": "Customer",
                    "party": invoice_doc.customer,
                    "reference_type": "Sales Invoice",
                    "reference_name": outstanding_invoice.name,
                    "debit_in_account_currency": row["credit_to_redeem"],
                    "cost_center": cost_center,
                }

                jv_credit_entry = {
                    "account": invoice_doc.debit_to,
                    "party_type": "Customer",
                    "party": invoice_doc.customer,
                    "reference_type": "Sales Invoice",
                    "reference_name": invoice_doc.name,
                    "credit_in_account_currency": row["credit_to_redeem"],
                    "cost_center": cost_center,
                }

                jv_doc.append("accounts", jv_debit_entry)
                jv_doc.append("accounts", jv_credit_entry)

                jv_doc.flags.ignore_permissions = True
                frappe.flags.ignore_account_permission = True
                jv_doc.set_missing_values()
                jv_doc.save()
                jv_doc.submit()

    if is_payment_entry and total_cash > 0:
        for payment in payments:
            if not payment.amount:
                continue
            payment_entry_doc = frappe.get_doc(
                {
                    "doctype": "Payment Entry",
                    "posting_date": today,
                    "payment_type": "Receive",
                    "party_type": "Customer",
                    "party": invoice_doc.customer,
                    "paid_amount": payment.amount,
                    "received_amount": payment.amount,
                    "paid_from": invoice_doc.debit_to,
                    "paid_to": payment.account,
                    "company": invoice_doc.company,
                    "mode_of_payment": payment.mode_of_payment,
                    "reference_no": invoice_doc.posa_pos_opening_shift,
                    "reference_date": today,
                }
            )

            payment_reference = {
                "allocated_amount": payment.amount,
                "due_date": data.get("due_date"),
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice_doc.name,
            }

            payment_entry_doc.append("references", payment_reference)
            payment_entry_doc.flags.ignore_permissions = True
            frappe.flags.ignore_account_permission = True
            payment_entry_doc.save()
            payment_entry_doc.submit()


def submit_in_background_job(kwargs):
    invoice = kwargs.get("invoice")
    invoice_doc = kwargs.get("invoice_doc")
    data = kwargs.get("data")
    is_payment_entry = kwargs.get("is_payment_entry")
    total_cash = kwargs.get("total_cash")
    cash_account = kwargs.get("cash_account")
    payments = kwargs.get("payments")

    invoice_doc = frappe.get_doc("Sales Invoice", invoice)
    
    # Update remarks with items details for background job
    items = []
    for item in invoice_doc.items:
        if item.item_name and item.rate and item.qty:
            total = item.rate * item.qty
            items.append(f"{item.item_name} - Rate: {item.rate}, Qty: {item.qty}, Amount: {total}")
    
    # Add the grand total at the end of remarks
    grand_total = f"\nGrand Total: {invoice_doc.grand_total}"
    items.append(grand_total)
    
    invoice_doc.remarks = "\n".join(items)
    invoice_doc.save()
    
    invoice_doc.submit()
    redeeming_customer_credit(
        invoice_doc, data, is_payment_entry, total_cash, cash_account, payments
    )


@frappe.whitelist()
def get_available_credit(customer, company):
    total_credit = []

    outstanding_invoices = frappe.get_all(
        "Sales Invoice",
        {
            "outstanding_amount": ["<", 0],
            "docstatus": 1,
            "is_return": 0,
            "customer": customer,
            "company": company,
        },
        ["name", "outstanding_amount"],
    )

    for row in outstanding_invoices:
        outstanding_amount = -(row.outstanding_amount)
        row = {
            "type": "Invoice",
            "credit_origin": row.name,
            "total_credit": outstanding_amount,
            "credit_to_redeem": 0,
        }

        total_credit.append(row)

    advances = frappe.get_all(
        "Payment Entry",
        {
            "unallocated_amount": [">", 0],
            "party_type": "Customer",
            "party": customer,
            "company": company,
            "docstatus": 1,
        },
        ["name", "unallocated_amount"],
    )

    for row in advances:
        row = {
            "type": "Advance",
            "credit_origin": row.name,
            "total_credit": row.unallocated_amount,
            "credit_to_redeem": 0,
        }

        total_credit.append(row)

    return total_credit


@frappe.whitelist()
def get_draft_invoices(pos_opening_shift):
    invoices_list = frappe.get_list(
        "Sales Invoice",
        filters={
            "posa_pos_opening_shift": pos_opening_shift,
            "docstatus": 0,
            "posa_is_printed": 0,
        },
        fields=["name"],
        limit_page_length=0,
        order_by="modified desc",
    )
    data = []
    for invoice in invoices_list:
        data.append(frappe.get_cached_doc("Sales Invoice", invoice["name"]))
    return data


@frappe.whitelist()
def delete_invoice(invoice):
    if frappe.get_value("Sales Invoice", invoice, "posa_is_printed"):
        frappe.throw(_("This invoice {0} cannot be deleted").format(invoice))
    frappe.delete_doc("Sales Invoice", invoice, force=1)
    return _("Invoice {0} Deleted").format(invoice)


@frappe.whitelist()
def get_items_details(pos_profile, items_data):
    _pos_profile = json.loads(pos_profile)
    ttl = _pos_profile.get("posa_server_cache_duration")
    if ttl:
        ttl = int(ttl) * 60

    @redis_cache(ttl=ttl or 1800)
    def __get_items_details(pos_profile, items_data):
        return _get_items_details(pos_profile, items_data)

    def _get_items_details(pos_profile, items_data):
        today = nowdate()
        pos_profile = json.loads(pos_profile)
        items_data = json.loads(items_data)
        warehouse = pos_profile.get("warehouse")
        result = []

        if len(items_data) > 0:
            for item in items_data:
                item_code = item.get("item_code")
                # Force refresh stock quantity on each request using proper cache clearing
                if hasattr(frappe.local.cache, "delete_key"):
                    frappe.local.cache.delete_key('bin_qty_cache')
                elif frappe.cache().get_value('bin_qty_cache'):
                    frappe.cache().delete_value('bin_qty_cache')
                
                item_stock_qty = get_stock_availability(item_code, warehouse)
                (has_batch_no, has_serial_no) = frappe.db.get_value(
                    "Item", item_code, ["has_batch_no", "has_serial_no"]
                )
                uoms = frappe.get_all(
                    "UOM Conversion Detail",
                    filters={"parent": item_code},
                    fields=["uom", "conversion_factor"],
                )

                # Add stock UOM if not already in uoms list
                stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
                if stock_uom:
                    stock_uom_exists = False
                    for uom_data in uoms:
                        if uom_data.get("uom") == stock_uom:
                            stock_uom_exists = True
                            break
                    
                    if not stock_uom_exists:
                        uoms.append({"uom": stock_uom, "conversion_factor": 1.0})

                serial_no_data = frappe.get_all(
                    "Serial No",
                    filters={
                        "item_code": item_code,
                        "status": "Active",
                        "warehouse": warehouse,
                    },
                    fields=["name as serial_no"],
                )

                batch_no_data = []

                batch_list = get_batch_qty(warehouse=warehouse, item_code=item_code)

                if batch_list:
                    for batch in batch_list:
                        if batch.qty > 0 and batch.batch_no:
                            batch_doc = frappe.get_cached_doc("Batch", batch.batch_no)
                            if (
                                str(batch_doc.expiry_date) > str(today)
                                or batch_doc.expiry_date in ["", None]
                            ) and batch_doc.disabled == 0:
                                batch_no_data.append(
                                    {
                                        "batch_no": batch.batch_no,
                                        "batch_qty": batch.qty,
                                        "expiry_date": batch_doc.expiry_date,
                                        "batch_price": batch_doc.posa_batch_price,
                                        "manufacturing_date": batch_doc.manufacturing_date,
                                    }
                                )

                row = {}
                row.update(item)
                row.update(
                    {
                        "item_uoms": uoms or [],
                        "serial_no_data": serial_no_data or [],
                        "batch_no_data": batch_no_data or [],
                        "actual_qty": item_stock_qty or 0,
                        "has_batch_no": has_batch_no,
                        "has_serial_no": has_serial_no,
                    }
                )

                result.append(row)

        return result

    # Skip cache to ensure fresh stock quantities on every request
    return _get_items_details(pos_profile, items_data)


@frappe.whitelist()
def get_item_detail(item, doc=None, warehouse=None, price_list=None):
    item = json.loads(item)
    today = nowdate()
    item_code = item.get("item_code")
    batch_no_data = []
    if warehouse and item.get("has_batch_no"):
        batch_list = get_batch_qty(warehouse=warehouse, item_code=item_code)
        if batch_list:
            for batch in batch_list:
                if batch.qty > 0 and batch.batch_no:
                    batch_doc = frappe.get_cached_doc("Batch", batch.batch_no)
                    if (
                        str(batch_doc.expiry_date) > str(today)
                        or batch_doc.expiry_date in ["", None]
                    ) and batch_doc.disabled == 0:
                        batch_no_data.append(
                            {
                                "batch_no": batch.batch_no,
                                "batch_qty": batch.qty,
                                "expiry_date": batch_doc.expiry_date,
                                "batch_price": batch_doc.posa_batch_price,
                                "manufacturing_date": batch_doc.manufacturing_date,
                            }
                        )

    item["selling_price_list"] = price_list

    max_discount = frappe.get_value("Item", item_code, "max_discount")
    res = get_item_details(
        item,
        doc,
        overwrite_warehouse=False,
    )
    if item.get("is_stock_item") and warehouse:
        res["actual_qty"] = get_stock_availability(item_code, warehouse)
    res["max_discount"] = max_discount
    res["batch_no_data"] = batch_no_data
    
    # Add UOMs data directly from item document
    uoms = frappe.get_all(
        "UOM Conversion Detail",
        filters={"parent": item_code},
        fields=["uom", "conversion_factor"],
    )
    
    # Add stock UOM if not already in uoms list
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    if stock_uom:
        stock_uom_exists = False
        for uom_data in uoms:
            if uom_data.get("uom") == stock_uom:
                stock_uom_exists = True
                break
        
        if not stock_uom_exists:
            uoms.append({"uom": stock_uom, "conversion_factor": 1.0})
    
    res["item_uoms"] = uoms
    
    return res


def get_stock_availability(item_code, warehouse):
    actual_qty = (
        frappe.db.get_value(
            "Stock Ledger Entry",
            filters={
                "item_code": item_code,
                "warehouse": warehouse,
                "is_cancelled": 0,
            },
            fieldname="qty_after_transaction",
            order_by="posting_date desc, posting_time desc, creation desc",
        )
        or 0.0
    )
    return actual_qty


@frappe.whitelist()
def create_customer(
    customer_id,
    customer_name,
    company,
    pos_profile_doc,
    tax_id=None,
    mobile_no=None,
    email_id=None,
    referral_code=None,
    birthday=None,
    customer_group=None,
    territory=None,
    customer_type=None,
    gender=None,
    method="create",
    address_line1=None,
    city=None,
    country=None,
):
    pos_profile = json.loads(pos_profile_doc)
    
    # Format birthday to MySQL compatible format (YYYY-MM-DD) if provided
    formatted_birthday = None
    if birthday:
        try:
            # Try to parse date in DD-MM-YYYY format
            if '-' in birthday:
                date_parts = birthday.split('-')
                if len(date_parts) == 3:
                    day, month, year = date_parts
                    formatted_birthday = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            # If format is already YYYY-MM-DD, use as is
            elif len(birthday) == 10 and birthday[4] == '-' and birthday[7] == '-':
                formatted_birthday = birthday
        except Exception:
            frappe.log_error(f"Error formatting birthday: {birthday}", "POS Awesome")
    
    if method == "create":
        
        is_exist = frappe.db.exists("Customer", {"customer_name": customer_name})
        if pos_profile.get("posa_allow_duplicate_customer_names") or not is_exist:
            
            customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "posa_referral_company": company,
                    "tax_id": tax_id,
                    "mobile_no": mobile_no,
                    "email_id": email_id,
                    "posa_referral_code": referral_code,
                    "posa_birthday": formatted_birthday,
                    "customer_type": customer_type,
                    "gender": gender,
                }
            )
            if customer_group:
                customer.customer_group = customer_group
            else:
                customer.customer_group = "All Customer Groups"
            if territory:
                customer.territory = territory
            else:
                customer.territory = "All Territories"

            customer.save()

            if address_line1 or city:
                args = {
                    "name": f"{customer.customer_name} - Shipping",
                    "doctype": "Customer",
                    "customer": customer.name,
                    "address_line1": address_line1 or "",
                    "address_line2": "",
                    "city": city or "",
                    "state": "",
                    "pincode": "",
                    "country": country or "",
                }
                make_address(json.dumps(args))

            return customer
        else:
            frappe.throw(_("Customer already exists"))

    elif method == "update":
        
        customer_doc = frappe.get_doc("Customer", customer_id)
        customer_doc.customer_name = customer_name
        customer_doc.tax_id = tax_id
        customer_doc.mobile_no = mobile_no
        customer_doc.email_id = email_id
        customer_doc.posa_referral_code = referral_code
        customer_doc.posa_birthday = formatted_birthday
        customer_doc.customer_type = customer_type
        customer_doc.gender = gender
        customer_doc.save()

        existing_address_name = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Customer", "link_name": customer_id},
            "parent"
        )

        if existing_address_name:
            
            address_doc = frappe.get_doc("Address", existing_address_name)
            address_doc.address_line1 = address_line1 or ""
            address_doc.city = city or ""
            address_doc.country = country or ""
            address_doc.save()
        else:
            
            if address_line1 or city:
                args = {
                    "name": f"{customer_doc.customer_name} - Shipping",
                    "doctype": "Customer",
                    "customer": customer_doc.name,
                    "address_line1": address_line1 or "",
                    "address_line2": "",
                    "city": city or "",
                    "state": "",
                    "pincode": "",
                    "country": country or "",
                }
                make_address(json.dumps(args))

        return customer_doc


@frappe.whitelist()
def get_items_from_barcode(selling_price_list, currency, barcode):
    search_item = frappe.get_all(
        "Item Barcode",
        filters={"barcode": barcode},
        fields=["parent", "barcode", "posa_uom"],
    )
    if len(search_item) == 0:
        return ""
    item_code = search_item[0].parent
    item_list = frappe.get_all(
        "Item",
        filters={"name": item_code},
        fields=[
            "name",
            "item_name",
            "description",
            "stock_uom",
            "image",
            "is_stock_item",
            "has_variants",
            "variant_of",
            "item_group",
            "has_batch_no",
            "has_serial_no",
        ],
    )

    if item_list[0]:
        item = item_list[0]
        filters = {"price_list": selling_price_list, "item_code": item_code}
        prices_with_uom = frappe.db.count(
            "Item Price",
            filters={
                "price_list": selling_price_list,
                "item_code": item_code,
                "uom": item.stock_uom,
            },
        )

        if prices_with_uom > 0:
            filters["uom"] = item.stock_uom
        else:
            filters["uom"] = ["in", ["", None, item.stock_uom]]

        item_prices_data = frappe.get_all(
            "Item Price",
            fields=["item_code", "price_list_rate", "currency"],
            filters=filters,
        )

        item_price = 0
        if len(item_prices_data):
            item_price = item_prices_data[0].get("price_list_rate")
            currency = item_prices_data[0].get("currency")

        item.update(
            {
                "rate": item_price,
                "currency": currency,
                "item_code": item_code,
                "barcode": barcode,
                "actual_qty": 0,
                "item_barcode": search_item,
            }
        )
        return item


@frappe.whitelist()
def set_customer_info(customer, fieldname, value=""):
    if fieldname == "loyalty_program":
        frappe.db.set_value("Customer", customer, "loyalty_program", value)

    contact = (
        frappe.get_cached_value("Customer", customer, "customer_primary_contact") or ""
    )

    if contact:
        contact_doc = frappe.get_doc("Contact", contact)
        if fieldname == "email_id":
            contact_doc.set("email_ids", [{"email_id": value, "is_primary": 1}])
            frappe.db.set_value("Customer", customer, "email_id", value)
        elif fieldname == "mobile_no":
            contact_doc.set("phone_nos", [{"phone": value, "is_primary_mobile_no": 1}])
            frappe.db.set_value("Customer", customer, "mobile_no", value)
        contact_doc.save()

    else:
        contact_doc = frappe.new_doc("Contact")
        contact_doc.first_name = customer
        contact_doc.is_primary_contact = 1
        contact_doc.is_billing_contact = 1
        if fieldname == "mobile_no":
            contact_doc.add_phone(value, is_primary_mobile_no=1, is_primary_phone=1)

        if fieldname == "email_id":
            contact_doc.add_email(value, is_primary=1)

        contact_doc.append("links", {"link_doctype": "Customer", "link_name": customer})

        contact_doc.flags.ignore_mandatory = True
        contact_doc.save()
        frappe.set_value(
            "Customer", customer, "customer_primary_contact", contact_doc.name
        )


@frappe.whitelist()
def search_invoices_for_return(invoice_name, company, customer_name=None, customer_id=None, 
                               mobile_no=None, tax_id=None, from_date=None, to_date=None, 
                               min_amount=None, max_amount=None, page=1):
    """
    Search for invoices that can be returned with separate customer search fields and pagination
    
    Args:
        invoice_name: Invoice ID to search for
        company: Company to search in
        customer_name: Customer name to search for
        customer_id: Customer ID to search for
        mobile_no: Mobile number to search for
        tax_id: Tax ID to search for
        from_date: Start date for filtering
        to_date: End date for filtering
        min_amount: Minimum invoice amount to filter by
        max_amount: Maximum invoice amount to filter by
        page: Page number for pagination (starts from 1)
    
    Returns:
        Dictionary with:
            - invoices: List of invoice documents
            - has_more: Boolean indicating if there are more invoices to load
    """
    # Start with base filters
    filters = {
        "company": company,
        "docstatus": 1,
        "is_return": 0,
    }
    
    # Convert page to integer if it's a string
    if page and isinstance(page, str):
        page = int(page)
    else:
        page = 1  # Default to page 1
    
    # Items per page - can be adjusted based on performance requirements
    page_length = 100
    start = (page - 1) * page_length
    
    # Add invoice name filter if provided
    if invoice_name:
        filters["name"] = ["like", f"%{invoice_name}%"]
    
    # Add date range filters if provided
    if from_date:
        filters["posting_date"] = [">=", from_date]
    
    if to_date:
        if "posting_date" in filters:
            filters["posting_date"] = ["between", [from_date, to_date]]
        else:
            filters["posting_date"] = ["<=", to_date]
    
    # Add amount filters if provided
    if min_amount:
        filters["grand_total"] = [">=", float(min_amount)]
    
    if max_amount:
        if "grand_total" in filters:
            # If min_amount was already set, change to between
            filters["grand_total"] = ["between", [float(min_amount), float(max_amount)]]
        else:
            filters["grand_total"] = ["<=", float(max_amount)]
    
    # If any customer search criteria is provided, find matching customers
    customer_ids = []
    if customer_name or customer_id or mobile_no or tax_id:
        conditions = []
        params = {}
        
        if customer_name:
            conditions.append("customer_name LIKE %(customer_name)s")
            params["customer_name"] = f"%{customer_name}%"
            
        if customer_id:
            conditions.append("name LIKE %(customer_id)s")
            params["customer_id"] = f"%{customer_id}%"
            
        if mobile_no:
            conditions.append("mobile_no LIKE %(mobile_no)s")
            params["mobile_no"] = f"%{mobile_no}%"
            
        if tax_id:
            conditions.append("tax_id LIKE %(tax_id)s")
            params["tax_id"] = f"%{tax_id}%"
        
        # Build the WHERE clause for the query
        where_clause = " OR ".join(conditions)
        customer_query = f"""
            SELECT name 
            FROM `tabCustomer`
            WHERE {where_clause}
            LIMIT 100
        """
        
        customers = frappe.db.sql(customer_query, params, as_dict=True)
        customer_ids = [c.name for c in customers]
        
        # If we found matching customers, add them to the filter
        if customer_ids:
            filters["customer"] = ["in", customer_ids]
        # If customer search criteria provided but no matches found, return empty
        elif any([customer_name, customer_id, mobile_no, tax_id]):
            return {"invoices": [], "has_more": False}
    
    # Count total invoices matching the criteria (for has_more flag)
    total_count_query = frappe.get_list(
        "Sales Invoice",
        filters=filters,
        fields=["count(name) as total_count"],
        as_list=False,
    )
    total_count = total_count_query[0].total_count if total_count_query else 0
    
    # Get invoices matching all criteria with pagination
    invoices_list = frappe.get_list(
        "Sales Invoice",
        filters=filters,
        fields=["name"],
        limit_start=start, 
        limit_page_length=page_length,
        order_by="posting_date desc, name desc",
    )
    
    # Process and return the results
    data = []
    
    # Process invoices and check for returns
    for invoice in invoices_list:
        invoice_doc = frappe.get_doc("Sales Invoice", invoice.name)
        
        # Check if any items have already been returned
        has_returns = frappe.get_all(
            "Sales Invoice",
            filters={
                "return_against": invoice.name,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if has_returns:
            # Get all returned items
            returned_items = []
            for ret_inv in has_returns:
                ret_doc = frappe.get_doc("Sales Invoice", ret_inv.name)
                for item in ret_doc.items:
                    returned_items.append(item.item_code)
            
            # Filter out returned items from original invoice
            filtered_items = []
            for item in invoice_doc.items:
                if item.item_code not in returned_items:
                    filtered_items.append(item)
            
            if filtered_items:
                # Create a copy of invoice with filtered items
                filtered_invoice = frappe.get_doc("Sales Invoice", invoice.name)
                filtered_invoice.items = filtered_items
                data.append(filtered_invoice)
        else:
            data.append(invoice_doc)
    
    # Check if there are more results
    has_more = (start + page_length) < total_count
    
    return {
        "invoices": data,
        "has_more": has_more
    }


@frappe.whitelist()
def search_orders(company, currency, order_name=None):
    filters = {
        "billing_status": ["in", ["Not Billed", "Partly Billed"]],
        "docstatus": 1,
        "company": company,
        "currency": currency,
    }
    if order_name:
        filters["name"] = ["like", f"%{order_name}%"]
    orders_list = frappe.get_list(
        "Sales Order",
        filters=filters,
        fields=["name"],
        limit_page_length=0,
        order_by="customer",
    )
    data = []
    for order in orders_list:
        data.append(frappe.get_doc("Sales Order", order["name"]))
    return data


def get_version():
    branch_name = get_app_branch("erpnext")
    if "12" in branch_name:
        return 12
    elif "13" in branch_name:
        return 13
    else:
        return 13


def get_app_branch(app):
    """Returns branch of an app"""
    import subprocess

    try:
        branch = subprocess.check_output(
            "cd ../apps/{0} && git rev-parse --abbrev-ref HEAD".format(app), shell=True
        )
        branch = branch.decode("utf-8")
        branch = branch.strip()
        return branch
    except Exception:
        return ""


@frappe.whitelist()
def get_offers(profile):
    pos_profile = frappe.get_doc("POS Profile", profile)
    company = pos_profile.company
    warehouse = pos_profile.warehouse
    date = nowdate()

    values = {
        "company": company,
        "pos_profile": profile,
        "warehouse": warehouse,
        "valid_from": date,
        "valid_upto": date,
    }
    data = frappe.db.sql(
        """
        SELECT *
        FROM `tabPOS Offer`
        WHERE 
        disable = 0 AND
        company = %(company)s AND
        (pos_profile is NULL OR pos_profile  = '' OR  pos_profile = %(pos_profile)s) AND
        (warehouse is NULL OR warehouse  = '' OR  warehouse = %(warehouse)s) AND
        (valid_from is NULL OR valid_from  = '' OR  valid_from <= %(valid_from)s) AND
        (valid_upto is NULL OR valid_from  = '' OR  valid_upto >= %(valid_upto)s)
    """,
        values=values,
        as_dict=1,
    )
    return data


@frappe.whitelist()
def get_customer_addresses(customer):
    return frappe.db.sql(
        """
        SELECT 
            address.name,
            address.address_line1,
            address.address_line2,
            address.address_title,
            address.city,
            address.state,
            address.country,
            address.address_type
        FROM `tabAddress` as address
        INNER JOIN `tabDynamic Link` AS link
				ON address.name = link.parent
        WHERE link.link_doctype = 'Customer'
            AND link.link_name = '{0}'
            AND address.disabled = 0
        ORDER BY address.name
        """.format(
            customer
        ),
        as_dict=1,
    )


@frappe.whitelist()
def make_address(args):
    args = json.loads(args)
    address = frappe.get_doc(
        {
            "doctype": "Address",
            "address_title": args.get("name"),
            "address_line1": args.get("address_line1"),
            "address_line2": args.get("address_line2"),
            "city": args.get("city"),
            "state": args.get("state"),
            "pincode": args.get("pincode"),
            "country": args.get("country"),
            "address_type": "Shipping",
            "links": [
                {"link_doctype": args.get("doctype"), "link_name": args.get("customer")}
            ],
        }
    ).insert()

    return address


def build_item_cache(item_code):
    parent_item_code = item_code

    attributes = [
        a.attribute
        for a in frappe.db.get_all(
            "Item Variant Attribute",
            {"parent": parent_item_code},
            ["attribute"],
            order_by="idx asc",
        )
    ]

    item_variants_data = frappe.db.get_all(
        "Item Variant Attribute",
        {"variant_of": parent_item_code},
        ["parent", "attribute", "attribute_value"],
        order_by="name",
        as_list=1,
    )

    disabled_items = set([i.name for i in frappe.db.get_all("Item", {"disabled": 1})])

    attribute_value_item_map = frappe._dict({})
    item_attribute_value_map = frappe._dict({})

    item_variants_data = [r for r in item_variants_data if r[0] not in disabled_items]
    for row in item_variants_data:
        item_code, attribute, attribute_value = row
        # (attr, value) => [item1, item2]
        attribute_value_item_map.setdefault((attribute, attribute_value), []).append(
            item_code
        )
        # item => {attr1: value1, attr2: value2}
        item_attribute_value_map.setdefault(item_code, {})[attribute] = attribute_value

    optional_attributes = set()
    for item_code, attr_dict in item_attribute_value_map.items():
        for attribute in attributes:
            if attribute not in attr_dict:
                optional_attributes.add(attribute)

    frappe.cache().hset(
        "attribute_value_item_map", parent_item_code, attribute_value_item_map
    )
    frappe.cache().hset(
        "item_attribute_value_map", parent_item_code, item_attribute_value_map
    )
    frappe.cache().hset("item_variants_data", parent_item_code, item_variants_data)
    frappe.cache().hset("optional_attributes", parent_item_code, optional_attributes)


def get_item_optional_attributes(item_code):
    val = frappe.cache().hget("optional_attributes", item_code)

    if not val:
        build_item_cache(item_code)

    return frappe.cache().hget("optional_attributes", item_code)


@frappe.whitelist()
def get_item_attributes(item_code):
    attributes = frappe.db.get_all(
        "Item Variant Attribute",
        fields=["attribute"],
        filters={"parenttype": "Item", "parent": item_code},
        order_by="idx asc",
    )

    optional_attributes = get_item_optional_attributes(item_code)

    for a in attributes:
        values = frappe.db.get_all(
            "Item Attribute Value",
            fields=["attribute_value", "abbr"],
            filters={"parenttype": "Item Attribute", "parent": a.attribute},
            order_by="idx asc",
        )
        a.values = values
        if a.attribute in optional_attributes:
            a.optional = True

    return attributes


@frappe.whitelist()
def create_payment_request(doc):
    doc = json.loads(doc)
    for pay in doc.get("payments"):
        if pay.get("type") == "Phone":
            if pay.get("amount") <= 0:
                frappe.throw(_("Payment amount cannot be less than or equal to 0"))

            if not doc.get("contact_mobile"):
                frappe.throw(_("Please enter the phone number first"))

            pay_req = get_existing_payment_request(doc, pay)
            if not pay_req:
                pay_req = get_new_payment_request(doc, pay)
                pay_req.submit()
            else:
                pay_req.request_phone_payment()

            return pay_req


def get_new_payment_request(doc, mop):
    payment_gateway_account = frappe.db.get_value(
        "Payment Gateway Account",
        {
            "payment_account": mop.get("account"),
        },
        ["name"],
    )

    args = {
        "dt": "Sales Invoice",
        "dn": doc.get("name"),
        "recipient_id": doc.get("contact_mobile"),
        "mode_of_payment": mop.get("mode_of_payment"),
        "payment_gateway_account": payment_gateway_account,
        "payment_request_type": "Inward",
        "party_type": "Customer",
        "party": doc.get("customer"),
        "return_doc": True,
    }
    return make_payment_request(**args)


def get_payment_gateway_account(args):
    return frappe.db.get_value(
        "Payment Gateway Account",
        args,
        ["name", "payment_gateway", "payment_account", "message"],
        as_dict=1,
    )


def get_existing_payment_request(doc, pay):
    payment_gateway_account = frappe.db.get_value(
        "Payment Gateway Account",
        {
            "payment_account": pay.get("account"),
        },
        ["name"],
    )

    args = {
        "doctype": "Payment Request",
        "reference_doctype": "Sales Invoice",
        "reference_name": doc.get("name"),
        "payment_gateway_account": payment_gateway_account,
        "email_to": doc.get("contact_mobile"),
    }
    pr = frappe.db.exists(args)
    if pr:
        return frappe.get_doc("Payment Request", pr)


def make_payment_request(**args):
    """Make payment request"""

    args = frappe._dict(args)

    ref_doc = frappe.get_doc(args.dt, args.dn)
    gateway_account = get_payment_gateway_account(args.get("payment_gateway_account"))
    if not gateway_account:
        frappe.throw(_("Payment Gateway Account not found"))

    grand_total = get_amount(ref_doc, gateway_account.get("payment_account"))
    if args.loyalty_points and args.dt == "Sales Order":
        from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
            validate_loyalty_points,
        )

        loyalty_amount = validate_loyalty_points(ref_doc, int(args.loyalty_points))
        frappe.db.set_value(
            "Sales Order",
            args.dn,
            "loyalty_points",
            int(args.loyalty_points),
            update_modified=False,
        )
        frappe.db.set_value(
            "Sales Order",
            args.dn,
            "loyalty_amount",
            loyalty_amount,
            update_modified=False,
        )
        grand_total = grand_total - loyalty_amount

    bank_account = (
        get_party_bank_account(args.get("party_type"), args.get("party"))
        if args.get("party_type")
        else ""
    )

    existing_payment_request = None
    if args.order_type == "Shopping Cart":
        existing_payment_request = frappe.db.get_value(
            "Payment Request",
            {
                "reference_doctype": args.dt,
                "reference_name": args.dn,
                "docstatus": ("!=", 2),
            },
        )

    if existing_payment_request:
        frappe.db.set_value(
            "Payment Request",
            existing_payment_request,
            "grand_total",
            grand_total,
            update_modified=False,
        )
        pr = frappe.get_doc("Payment Request", existing_payment_request)
    else:
        if args.order_type != "Shopping Cart":
            existing_payment_request_amount = get_existing_payment_request_amount(
                args.dt, args.dn
            )

            if existing_payment_request_amount:
                grand_total -= existing_payment_request_amount

        pr = frappe.new_doc("Payment Request")
        pr.update(
            {
                "payment_gateway_account": gateway_account.get("name"),
                "payment_gateway": gateway_account.get("payment_gateway"),
                "payment_account": gateway_account.get("payment_account"),
                "payment_channel": gateway_account.get("payment_channel"),
                "payment_request_type": args.get("payment_request_type"),
                "currency": ref_doc.currency,
                "grand_total": grand_total,
                "mode_of_payment": args.mode_of_payment,
                "email_to": args.recipient_id or ref_doc.owner,
                "subject": _("Payment Request for {0}").format(args.dn),
                "message": gateway_account.get("message") or get_dummy_message(ref_doc),
                "reference_doctype": args.dt,
                "reference_name": args.dn,
                "party_type": args.get("party_type") or "Customer",
                "party": args.get("party") or ref_doc.get("customer"),
                "bank_account": bank_account,
            }
        )

        if args.order_type == "Shopping Cart" or args.mute_email:
            pr.flags.mute_email = True

        pr.insert(ignore_permissions=True)
        if args.submit_doc:
            pr.submit()

    if args.order_type == "Shopping Cart":
        frappe.db.commit()
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = pr.get_payment_url()

    if args.return_doc:
        return pr

    return pr.as_dict()


def get_amount(ref_doc, payment_account=None):
    """get amount based on doctype"""
    grand_total = 0
    for pay in ref_doc.payments:
        if pay.type == "Phone" and pay.account == payment_account:
            grand_total = pay.amount
            break

    if grand_total > 0:
        return grand_total

    else:
        frappe.throw(
            _("Payment Entry is already created or payment account is not matched")
        )


@frappe.whitelist()
def get_pos_coupon(coupon, customer, company):
    res = check_coupon_code(coupon, customer, company)
    return res


@frappe.whitelist()
def get_active_gift_coupons(customer, company):
    coupons = []
    coupons_data = frappe.get_all(
        "POS Coupon",
        filters={
            "company": company,
            "coupon_type": "Gift Card",
            "customer": customer,
            "used": 0,
        },
        fields=["coupon_code"],
    )
    if len(coupons_data):
        coupons = [i.coupon_code for i in coupons_data]
    return coupons


@frappe.whitelist()
def get_customer_info(customer):
    customer = frappe.get_doc("Customer", customer)

    res = {"loyalty_points": None, "conversion_factor": None}

    res["email_id"] = customer.email_id
    res["mobile_no"] = customer.mobile_no
    res["image"] = customer.image
    res["loyalty_program"] = customer.loyalty_program
    res["customer_price_list"] = customer.default_price_list
    res["customer_group"] = customer.customer_group
    res["customer_type"] = customer.customer_type
    res["territory"] = customer.territory
    res["birthday"] = customer.posa_birthday
    res["gender"] = customer.gender
    res["tax_id"] = customer.tax_id
    res["posa_discount"] = customer.posa_discount
    res["name"] = customer.name
    res["customer_name"] = customer.customer_name
    res["customer_group_price_list"] = frappe.get_value(
        "Customer Group", customer.customer_group, "default_price_list"
    )

    if customer.loyalty_program:
        lp_details = get_loyalty_program_details_with_points(
            customer.name,
            customer.loyalty_program,
            silent=True,
            include_expired_entry=False,
        )
        res["loyalty_points"] = lp_details.get("loyalty_points")
        res["conversion_factor"] = lp_details.get("conversion_factor")
        
    addresses = frappe.db.sql(
        """
        SELECT
            address.name as address_name,
            address.address_line1,
            address.address_line2,
            address.city,
            address.state,
            address.country,
            address.address_type
        FROM `tabAddress` address
        INNER JOIN `tabDynamic Link` link
            ON (address.name = link.parent)
        WHERE
            link.link_doctype = 'Customer'
            AND link.link_name = %s
            AND address.disabled = 0
            AND address.address_type = 'Shipping'
        ORDER BY address.creation DESC
        LIMIT 1
        """,
        (customer.name,),
        as_dict=True
    )

    if addresses:
        
        addr = addresses[0]
        res["address_line1"] = addr.address_line1 or ""
        res["address_line2"] = addr.address_line2 or ""
        res["city"] = addr.city or ""
        res["state"] = addr.state or ""
        res["country"] = addr.country or ""

    return res


def get_company_domain(company):
    return frappe.get_cached_value("Company", cstr(company), "domain")


@frappe.whitelist()
def get_applicable_delivery_charges(
    company, pos_profile, customer, shipping_address_name=None
):
    return _get_applicable_delivery_charges(
        company, pos_profile, customer, shipping_address_name
    )


def auto_create_items():
    # create 20000 items
    for i in range(20000):
        item_code = "AUTO-ITEM-{}".format(i)
        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code,
                "description": item_code,
                "item_group": "Auto Items",
                "is_stock_item": 0,
                "stock_uom": "Nos",
                "is_sales_item": 1,
                "is_purchase_item": 0,
                "is_fixed_asset": 0,
                "is_sub_contracted_item": 0,
                "is_pro_applicable": 0,
                "is_manufactured_item": 0,
                "is_service_item": 0,
                "is_non_stock_item": 0,
                "is_batch_item": 0,
                "is_table_item": 0,
                "is_variant_item": 0,
                "is_stock_item": 1,
                "opening_stock": 1000,
                "valuation_rate": 50 + i,
                "standard_rate": 100 + i,
            }
        )
        print("Creating Item: {}".format(item_code))
        item.insert(ignore_permissions=True)
        frappe.db.commit()


@frappe.whitelist()
def search_serial_or_batch_or_barcode_number(search_value, search_serial_no):
    # search barcode no
    barcode_data = frappe.db.get_value(
        "Item Barcode",
        {"barcode": search_value},
        ["barcode", "parent as item_code"],
        as_dict=True,
    )
    if barcode_data:
        return barcode_data
    # search serial no
    if search_serial_no:
        serial_no_data = frappe.db.get_value(
            "Serial No", search_value, ["name as serial_no", "item_code"], as_dict=True
        )
        if serial_no_data:
            return serial_no_data
    # search batch no
    batch_no_data = frappe.db.get_value(
        "Batch", search_value, ["name as batch_no", "item as item_code"], as_dict=True
    )
    if batch_no_data:
        return batch_no_data
    return {}


def get_seearch_items_conditions(item_code, serial_no, batch_no, barcode):
    if serial_no or batch_no or barcode:
        return " and name = {0}".format(frappe.db.escape(item_code))
    return """ and (name like {item_code} or item_name like {item_code})""".format(
        item_code=frappe.db.escape("%" + item_code + "%")
    )


@frappe.whitelist()
def create_sales_invoice_from_order(sales_order):
    sales_invoice = make_sales_invoice(sales_order, ignore_permissions=True)
    sales_invoice.save()
    return sales_invoice


@frappe.whitelist()
def delete_sales_invoice(sales_invoice):
    frappe.delete_doc("Sales Invoice", sales_invoice)


@frappe.whitelist()
def get_sales_invoice_child_table(sales_invoice, sales_invoice_item):
    parent_doc = frappe.get_doc("Sales Invoice", sales_invoice)
    child_doc = frappe.get_doc(
        "Sales Invoice Item", {"parent": parent_doc.name, "name": sales_invoice_item}
    )
    return child_doc

@frappe.whitelist()
def update_invoice_from_order(data):
     data = json.loads(data)
     invoice_doc = frappe.get_doc("Sales Invoice", data.get("name"))
     invoice_doc.update(data)
     invoice_doc.save()
     return invoice_doc

@frappe.whitelist()
def validate_return_items(return_against, items):
     """Custom validation for return items"""
     # If no return_against (return without invoice), skip validation
     if not return_against:
         return {"valid": True}
         
     original_invoice = frappe.get_doc("Sales Invoice", return_against)
     
     # Create lookup for original items
     original_items = {}
     for item in original_invoice.items:
         # Use item_code as key since that's what we're matching against
         if item.item_code not in original_items:
             original_items[item.item_code] = {
                 'qty': item.qty,
                 'rate': item.rate
             }
         else:
             original_items[item.item_code]['qty'] += item.qty
 
     # Validate return items
     for item in items:
         item_code = item.get('item_code')
         if item_code not in original_items:
             return {
                 "valid": False,
                 "message": f"Item {item_code} not found in original invoice"
             }
         
         return_qty = abs(float(item.get('qty')))
         if return_qty > original_items[item_code]['qty']:
             return {
                 "valid": False, 
                 "message": f"Return quantity {return_qty} exceeds original quantity {original_items[item_code]['qty']} for item {item_code}"
             }
             
         original_items[item_code]['qty'] -= return_qty
 
     return {"valid": True}

@frappe.whitelist()
def get_available_currencies():
    """Get list of available currencies from ERPNext"""
    return frappe.get_all("Currency", fields=["name", "currency_name"], 
                         filters={"enabled": 1}, order_by="currency_name")




@frappe.whitelist()
def get_app_info() -> Dict[str, List[Dict[str, str]]]:
    """
    Return a list of installed apps and their versions,
    as recorded in the Installed Application DocType.
    """
    # Fetch raw records from the DocType
    app_records = frappe.get_all(
        "Installed Application",
        fields=["app_name", "app_version"],
        order_by="app_name asc"
    )

    # Transform into the shape your API expects
    apps_info = [
        {
            "app_name": record["app_name"],
            "installed_version": record["app_version"]
        }
        for record in app_records
    ]

    return {"apps": apps_info}
