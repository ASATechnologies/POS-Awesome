<template>
  <!-- Main Invoice Wrapper -->
  <div>
    <!-- Cancel Sale Confirmation Dialog -->
    <v-dialog v-model="cancel_dialog" max-width="330">
      <v-card>
        <v-card-title class="text-h5">
          <span class="text-h5 text-primary">{{
            __("Cancel Sale ?")
            }}</span>
        </v-card-title>
        <v-card-text>
          This would cancel and delete the current sale. To save it as Draft, click the "Save and Clear" instead.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" @click="cancel_invoice">
            {{ __("Yes, Cancel sale") }}
          </v-btn>
          <v-btn color="warning" @click="cancel_dialog = false">
            {{ __("Back") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Main Invoice Card (contains all invoice content) -->
    <v-card style="max-height: 70vh; height: 70vh"
      :class="['cards my-0 py-0 mt-3 bg-grey-lighten-5', { 'return-mode': invoiceType === 'Return' }]">
      <!-- Top Row: Customer Selection and Invoice Type -->
      <v-row align="center" class="items px-2 py-1">
        <v-col :cols="pos_profile.posa_allow_sales_order ? 9 : 12" class="pb-2 pr-0">
          <!-- Customer selection component -->
          <Customer />
        </v-col>
        <!-- Invoice Type Selection (Only shown if sales orders are allowed) -->
        <v-col v-if="pos_profile.posa_allow_sales_order" cols="3" class="pb-2">
          <v-select density="compact" hide-details variant="outlined" color="primary" bg-color="white"
            :items="invoiceTypes" :label="frappe._('Type')" v-model="invoiceType"
            :disabled="invoiceType == 'Return'"></v-select>
        </v-col>
      </v-row>

      <!-- Delivery Charges Section (Only if enabled in POS profile) -->
      <v-row align="center" class="items px-2 py-1 mt-0 pt-0" v-if="pos_profile.posa_use_delivery_charges">
        <v-col cols="8" class="pb-0 mb-0 pr-0 pt-0">
          <!-- Delivery Charges Selection Dropdown -->
          <v-autocomplete density="compact" clearable auto-select-first variant="outlined" color="primary"
            :label="frappe._('Delivery Charges')" v-model="selected_delivery_charge" :items="delivery_charges"
            item-title="name" item-value="name" return-object bg-color="white" :no-data-text="__('Charges not found')"
            hide-details :customFilter="deliveryChargesFilter" :disabled="readonly"
            @update:model-value="update_delivery_charges()">
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props">
                <v-list-item-title class="text-primary text-subtitle-1" v-html="item.raw.name"></v-list-item-title>
                <v-list-item-subtitle v-html="`Rate: ${item.raw.rate}`"></v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-autocomplete>
        </v-col>
        <!-- Delivery Charges Rate Display -->
        <v-col cols="4" class="pb-0 mb-0 pt-0">
          <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Delivery Charges Rate')"
            bg-color="white" hide-details :model-value="formatCurrency(delivery_charges_rate)"
            :prefix="currencySymbol(pos_profile.currency)" disabled></v-text-field>
        </v-col>
      </v-row>

      <!-- Posting Date and Customer Balance Section -->
      <v-row align="center" class="items px-2 py-1 mt-0 pt-0" v-if="pos_profile.posa_allow_change_posting_date">
        <!-- Posting Date Selection with Date Picker -->
        <v-col cols="6" class="pb-2">
          <v-menu v-model="posting_date_menu" :close-on-content-click="false" transition="scale-transition"
            density="default">
            <template v-slot:activator="{ props }">
              <v-text-field v-model="formatted_posting_date" :label="frappe._('Posting Date')" readonly
                variant="solo" density="compact" clearable color="primary" hide-details
                prepend-inner-icon="mdi-calendar"
                v-bind="props"></v-text-field>
            </template>
            <v-date-picker v-model="posting_date" no-title scrollable color="primary"
              :min="frappe.datetime.add_days(frappe.datetime.nowdate(true), -7)"
              :max="frappe.datetime.add_days(frappe.datetime.nowdate(true), 7)">
              <template #actions>
                <v-spacer></v-spacer>
                <v-btn text color="primary" @click="posting_date = null; posting_date_menu = false">{{ __('Clear')
                  }}</v-btn>
                <v-btn text color="primary" @click="posting_date_menu = false">{{ __('OK') }}</v-btn>
              </template>
            </v-date-picker>
          </v-menu>
        </v-col>
        <!-- Customer Balance Display (Only if enabled in POS profile) -->
        <v-col v-if="pos_profile.posa_show_customer_balance" cols="6" class="pb-2 d-flex align-center">
          <div class="balance-field">
            <strong>Balance:</strong>
            <span class="balance-value">{{ formatCurrency(customer_balance) }}</span>
          </div>
        </v-col>
      </v-row>

      <!-- Multi-Currency Section (Only if enabled in POS profile) -->
      <v-row align="center" class="items px-2 py-1 mt-0 pt-0" v-if="pos_profile.posa_allow_multi_currency">
        <!-- Currency Selection Dropdown -->
        <v-col cols="4" class="pb-2">
          <v-select density="compact" variant="outlined" color="primary" :label="frappe._('Currency')" bg-color="white"
            hide-details v-model="selected_currency" :items="available_currencies"
            @update:model-value="update_currency"></v-select>
        </v-col>
        <!-- Exchange Rate Input Field -->
        <v-col cols="4" class="pb-2">
          <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Exchange Rate')"
            bg-color="white" hide-details v-model="exchange_rate" :rules="[isNumber]"
            @change="update_exchange_rate"></v-text-field>
        </v-col>
      </v-row>

      <!-- Items Table Section (Main items list for invoice) -->
      <div class="my-0 py-0 overflow-y-auto mt-3" style="max-height: calc(70vh - 180px)">
        <!-- Main Items Data Table -->
        <v-data-table 
          :headers="items_headers" 
          :items="items" 
          v-model:expanded="expanded" 
          show-expand
          item-value="posa_row_id" 
          class="elevation-1" 
          :items-per-page="itemsPerPage" 
          expand-on-click
          density="compact" 
          hide-default-footer
          :single-expand="true"
          @update:expanded="handleExpandedUpdate">
          <!-- Quantity Column Template -->
          <template v-slot:item.qty="{ item }">{{
            formatFloat(item.qty)
          }}</template>
          <!-- Rate Column Template with Currency Symbol -->
          <template v-slot:item.rate="{ item }">
            <div class="d-flex align-center">
              <span>{{ currencySymbol(displayCurrency) }}</span>
              <span>{{ formatCurrency(item.rate) }}</span>
            </div>
          </template>
          <!-- Amount Column Template with Currency Symbol -->
          <template v-slot:item.amount="{ item }">
            <div class="d-flex align-center">
              <span>{{ currencySymbol(displayCurrency) }}</span>
              <span>{{ formatCurrency(item.qty * item.rate) }}</span>
            </div>
          </template>
          <!-- Discount Amount Column Template -->
          <template v-slot:item.discount_amount="{ item }">
            <div class="d-flex align-center">
              <span>{{ currencySymbol(displayCurrency) }}</span>
              <span>{{ formatCurrency(item.discount_amount) }}</span>
            </div>
          </template>
          <!-- Price List Rate Column Template -->
          <template v-slot:item.price_list_rate="{ item }">
            <div class="d-flex align-center">
              <span>{{ currencySymbol(displayCurrency) }}</span>
              <span>{{ formatCurrency(item.price_list_rate) }}</span>
            </div>
          </template>
          <!-- Offer Checkbox Column Template -->
          <template v-slot:item.posa_is_offer="{ item }">
            <v-checkbox-btn v-model="item.posa_is_offer" class="center" @change="toggleOffer(item)"></v-checkbox-btn>
          </template>

          <!-- Expanded Row Template for Item Details -->
          <template v-slot:expanded-row="{ columns: headers, item }">
            <td :colspan="headers.length" class="ma-0 pa-2">
              <!-- Expanded Item Action Buttons Row -->
              <v-row class="mb-2" dense>
                <v-col cols="auto">
                  <v-btn :disabled="!!item.posa_is_replace" icon="mdi-delete" size="large" color="error" variant="tonal" class="mr-2" width="52" height="52" @click.stop="remove_item(item)">
                    <v-icon size="large">mdi-delete</v-icon>
                  </v-btn>
                </v-col>
                <v-spacer></v-spacer>
                <v-col cols="auto">
                  <v-btn-group density="default" class="mx-2">
                    <v-btn :disabled="!!item.posa_is_replace" size="large" color="error" variant="tonal" width="52" height="52" class="mr-1" @click.stop="subtract_one(item)">
                      <v-icon size="large">mdi-minus</v-icon>
                    </v-btn>
                    <v-btn :disabled="!!item.posa_is_replace" size="large" color="success" variant="tonal" width="52" height="52" class="ml-1" @click.stop="add_one(item)">
                      <v-icon size="large">mdi-plus</v-icon>
                    </v-btn>
                  </v-btn-group>
                </v-col>
              </v-row>

              <!-- Expanded Item Details Form Row -->
              <v-row dense class="mb-1">
                <!-- First Row -->
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Item Code')"
                    bg-color="white" hide-details v-model="item.item_code" disabled></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('QTY')"
                    bg-color="white" hide-details :model-value="formatFloat(item.qty)" @change="
                      [
                        setFormatedQty(item, 'qty', null, false, $event.target.value),
                        calc_stock_qty(item, item.qty),
                      ]" :rules="[isNumber]" :disabled="!!item.posa_is_replace"></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-select density="compact" bg-color="white" :label="frappe._('UOM')" v-model="item.uom"
                    :items="item.item_uoms" variant="outlined" item-title="uom" item-value="uom" hide-details
                    @update:model-value="calc_uom(item, $event)" :disabled="!!item.posa_is_replace ||
                      (invoiceType === 'Return' && invoice_doc.return_against)"></v-select>
                </v-col>

                <!-- Second Row -->
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Rate')"
                    bg-color="white" hide-details :prefix="currencySymbol(pos_profile.currency)"
                    :model-value="formatCurrency(item.rate)" @change="
                      [
                        setFormatedCurrency(item, 'rate', null, false, $event),
                        calc_prices(item, $event.target.value, $event),
                      ]" :rules="[isNumber]" id="rate" :disabled="!!item.posa_is_replace ||
                        !!item.posa_offer_applied ||
                        !pos_profile.posa_allow_user_to_edit_rate ||
                        (invoiceType === 'Return' && invoice_doc.return_against)"></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Discount %')"
                    bg-color="white" hide-details :model-value="formatFloat(item.discount_percentage)" @change="
                      [
                        setFormatedCurrency(item, 'discount_percentage', null, true, $event),
                        calc_prices(item, $event.target.value, $event),
                      ]" :rules="[isNumber]" id="discount_percentage" :disabled="!!item.posa_is_replace ||
                        item.posa_offer_applied ||
                        !pos_profile.posa_allow_user_to_edit_item_discount ||
                        (invoiceType === 'Return' && invoice_doc.return_against)" suffix="%"></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Discount Amount')"
                    bg-color="white" hide-details :model-value="formatCurrency(item.discount_amount || 0)" ref="discount"
                    @change="(event) => { if (expanded && expanded.length === 1 && expanded[0] === item.posa_row_id) { calc_prices(item, event.target.value, { target: { id: 'discount_amount' } }); } }" 
                    :rules="['isNumber']" id="discount_amount" 
                    :disabled="!!item.posa_is_replace || item.posa_offer_applied || !pos_profile.posa_allow_user_to_edit_item_discount || (invoiceType === 'Return' && invoice_doc.return_against)" 
                    :prefix="currencySymbol(pos_profile.currency)"></v-text-field>
                </v-col>

                <!-- Third Row -->
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Price list Rate')"
                    bg-color="white" hide-details :model-value="formatCurrency(item.price_list_rate)" disabled
                    :prefix="currencySymbol(pos_profile.currency)"></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Available QTY')"
                    bg-color="white" hide-details :model-value="formatFloat(item.actual_qty)" disabled></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Group')"
                    bg-color="white" hide-details v-model="item.item_group" disabled></v-text-field>
                </v-col>

                <!-- Fourth Row -->
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Stock QTY')"
                    bg-color="white" hide-details :model-value="formatFloat(item.stock_qty)" disabled></v-text-field>
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Stock UOM')"
                    bg-color="white" hide-details v-model="item.stock_uom" disabled></v-text-field>
                </v-col>
                <v-col cols="12" sm="4" v-if="item.posa_offer_applied">
                  <v-checkbox density="compact" :label="frappe._('Offer Applied')" v-model="item.posa_offer_applied"
                    readonly hide-details class="mt-1"></v-checkbox>
                </v-col>

                <!-- Serial Number Fields (if enabled) -->
                <template v-if="item.has_serial_no == 1 || item.serial_no">
                  <v-col cols="12" sm="4">
                    <v-text-field density="compact" variant="outlined" color="primary" :label="frappe._('Serial No QTY')"
                      bg-color="white" hide-details v-model="item.serial_no_selected_count" type="number"
                      disabled></v-text-field>
                  </v-col>
                  <v-col cols="12">
                    <v-autocomplete v-model="item.serial_no_selected" :items="item.serial_no_data" item-title="serial_no"
                      variant="outlined" density="compact" chips color="primary" small-chips
                      :label="frappe._('Serial No')" multiple @update:model-value="set_serial_no(item)"></v-autocomplete>
                  </v-col>
                </template>

                <!-- Batch Number Fields (if enabled) -->
                <template v-if="item.has_batch_no == 1 || item.batch_no">
                  <v-col cols="12" sm="4">
                    <v-text-field density="compact" variant="outlined" color="primary"
                      :label="frappe._('Batch No. Available QTY')" bg-color="white" hide-details
                      :model-value="formatFloat(item.actual_batch_qty)" disabled></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field density="compact" variant="outlined" color="primary"
                      :label="frappe._('Batch No Expiry Date')" bg-color="white" hide-details
                      v-model="item.batch_no_expiry_date" disabled></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-autocomplete v-model="item.batch_no" :items="item.batch_no_data" item-title="batch_no"
                      variant="outlined" density="compact" color="primary" :label="frappe._('Batch No')"
                      @update:model-value="set_batch_qty(item, $event)" hide-details>
                      <template v-slot:item="{ props, item }">
                        <v-list-item v-bind="props">
                          <v-list-item-title v-html="item.raw.batch_no"></v-list-item-title>
                          <v-list-item-subtitle v-html="`Available QTY  '${item.raw.batch_qty}' - Expiry Date ${item.raw.expiry_date}`
                            "></v-list-item-subtitle>
                        </v-list-item>
                      </template>
                    </v-autocomplete>
                  </v-col>
                </template>

                <!-- Delivery Date (if sales order and order type) -->
                <v-col cols="12" sm="4" v-if="pos_profile.posa_allow_sales_order && invoiceType == 'Order'">
                  <v-menu ref="item_delivery_date" v-model="item.item_delivery_date" :close-on-content-click="false"
                    v-model:return-value="item.posa_delivery_date" transition="scale-transition">
                    <template v-slot:activator="{ props }">
                      <v-text-field v-model="item.posa_delivery_date" :label="frappe._('Delivery Date')" readonly
                        variant="outlined" density="compact" clearable color="primary" hide-details
                        v-bind="props"></v-text-field>
                    </template>
                    <v-date-picker v-model="item.posa_delivery_date" no-title scrollable color="primary"
                      :min="frappe.datetime.now_date()">
                      <v-spacer></v-spacer>
                      <v-btn variant="text" color="primary" @click="item.item_delivery_date = false">
                        Cancel
                      </v-btn>
                      <v-btn variant="text" color="primary" @click="
                        [
                          $refs.item_delivery_date.save(item.posa_delivery_date),
                          validate_due_date(item),
                        ]">
                        OK
                      </v-btn>
                    </v-date-picker>
                  </v-menu>
                </v-col>
              </v-row>
            </td>
          </template>
        </v-data-table>
      </div>
    </v-card>
    <v-card class="cards mb-0 mt-3 py-2 px-3 rounded-lg bg-grey-lighten-4">
      <v-row dense>
        <!-- Summary Info -->
        <v-col cols="12" md="7">
          <v-row dense>
            <!-- Total Qty -->
            <v-col cols="6">
              <v-text-field :model-value="formatFloat(total_qty)" :label="frappe._('Total Qty')"
                prepend-inner-icon="mdi-format-list-numbered" variant="solo" density="compact" readonly
                color="accent" />
            </v-col>
            <!-- Additional Discount (Amount or Percentage) -->
            <v-col cols="6" v-if="!pos_profile.posa_use_percentage_discount">
              <v-text-field v-model="additional_discount" :label="frappe._('Additional Discount')"
                prepend-inner-icon="mdi-cash-minus" variant="solo" density="compact" color="warning"
                :prefix="currencySymbol(pos_profile.currency)"
                :disabled="!pos_profile.posa_allow_user_to_edit_additional_discount" />
            </v-col>

            <v-col cols="6" v-else>
              <v-text-field v-model="additional_discount_percentage" @change="update_discount_umount()"
                :rules="[isNumber]" :label="frappe._('Additional Discount %')" suffix="%"
                prepend-inner-icon="mdi-percent" variant="solo" density="compact" color="warning"
                :disabled="!pos_profile.posa_allow_user_to_edit_additional_discount || !!discount_percentage_offer_name" />
            </v-col>

            <!-- Items Discount -->
            <v-col cols="6">
              <v-text-field :model-value="formatCurrency(total_items_discount_amount)"
                :prefix="currencySymbol(displayCurrency)" :label="frappe._('Items Discounts')" 
                prepend-inner-icon="mdi-tag-minus" variant="solo" density="compact" color="warning" readonly />
            </v-col>

            <!-- Total (moved to maintain row alignment) -->
            <v-col cols="6">
              <v-text-field :model-value="formatCurrency(subtotal)" :prefix="currencySymbol(displayCurrency)"
                :label="frappe._('Total')" prepend-inner-icon="mdi-cash" variant="solo" density="compact" readonly
                color="success" />
            </v-col>
          </v-row>
        </v-col>

        <!-- Action Buttons -->
        <v-col cols="12" md="5">
          <v-row dense>
            <v-col cols="6">
              <v-btn block color="accent" theme="dark" prepend-icon="mdi-content-save" @click="save_and_clear_invoice">
                {{ __("Save & Clear") }}
              </v-btn>
            </v-col>
            <v-col cols="6">
              <v-btn block color="warning" theme="dark" prepend-icon="mdi-file-document" @click="get_draft_invoices">
                {{ __("Load Drafts") }}
              </v-btn>
            </v-col>
            <v-col cols="6" v-if="pos_profile.custom_allow_select_sales_order === 1">
              <v-btn block color="info" theme="dark" prepend-icon="mdi-book-search" @click="get_draft_orders">
                {{ __("Select S.O") }}
              </v-btn>
            </v-col>
            <v-col cols="6">
              <v-btn block color="error" theme="dark" prepend-icon="mdi-close-circle" @click="cancel_dialog = true">
                {{ __("Cancel Sale") }}
              </v-btn>
            </v-col>
            <v-col cols="6" v-if="pos_profile.posa_allow_return == 1">
              <v-btn block color="secondary" theme="dark" prepend-icon="mdi-backup-restore" @click="open_returns">
                {{ __("Sales Return") }}
              </v-btn>
            </v-col>
            <v-col cols="6" v-if="pos_profile.posa_allow_print_draft_invoices">
              <v-btn block color="primary" theme="dark" prepend-icon="mdi-printer" @click="print_draft_invoice">
                {{ __("Print Draft") }}
              </v-btn>
            </v-col>
            <v-col cols="12">
              <v-btn block color="success" theme="dark" size="large" prepend-icon="mdi-credit-card"
                @click="show_payment">
                {{ __("PAY") }}
              </v-btn>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </v-card>
  </div>
</template>

<script>

import format from "../../format";
import Customer from "./Customer.vue";

export default {
  mixins: [format],
  data() {
    return {
      // POS profile settings
      pos_profile: "",
      pos_opening_shift: "",
      stock_settings: "",
      invoice_doc: "",
      return_doc: "",
      customer: "",
      customer_info: "",
      customer_balance: 0,
      discount_amount: 0,
      additional_discount: 0,
      additional_discount_percentage: 0,
      total_tax: 0,
      items: [], // List of invoice items
      posOffers: [], // All available offers
      posa_offers: [], // Offers applied to this invoice
      posa_coupons: [], // Coupons applied
      allItems: [], // All items for offer logic
      discount_percentage_offer_name: null, // Track which offer is applied
      invoiceTypes: ["Invoice", "Order"], // Types of invoices
      invoiceType: "Invoice", // Current invoice type
      itemsPerPage: 1000, // Items per page in table
      expanded: [], // Array of expanded row IDs
      singleExpand: true, // Only one row expanded at a time
      cancel_dialog: false, // Cancel dialog visibility
      float_precision: 6, // Float precision for calculations
      currency_precision: 6, // Currency precision for display
      new_line: false, // Add new line for item
      delivery_charges: [], // List of delivery charges
      delivery_charges_rate: 0, // Selected delivery charge rate
      selected_delivery_charge: "", // Selected delivery charge object
      invoice_posting_date: false, // Posting date dialog
      posting_date: frappe.datetime.nowdate(), // Invoice posting date
      posting_date_menu: false, // Posting date menu visibility
      items_headers: [
        // Table headers for items
        {
          title: __("Name"),
          align: "start",
          sortable: true,
          key: "item_name",
        },
        { title: __("QTY"), key: "qty", align: "center" },
        { title: __("UOM"), key: "uom", align: "center" },
        { title: __("Rate"), key: "rate", align: "center" },
        { title: __("Amount"), key: "amount", align: "center" },
        { title: __("Offer?"), key: "posa_is_offer", align: "center" },
      ],
      selected_currency: "", // Currently selected currency
      exchange_rate: 1, // Current exchange rate
      available_currencies: [], // List of available currencies
    };
  },

  components: {
    Customer,
  },

  computed: {
    // Calculate total quantity of all items
    total_qty() {
      this.close_payments();
      let qty = 0;
      this.items.forEach((item) => {
        qty += flt(item.qty);
      });
      return this.flt(qty, this.float_precision);
    },
    // Calculate total amount for all items (handles returns)
    Total() {
      let sum = 0;
      this.items.forEach((item) => {
        // For returns, use absolute value for correct calculation
        const qty = this.invoiceType === "Return" ? Math.abs(flt(item.qty)) : flt(item.qty);
        const rate = flt(item.rate);
        sum += qty * rate;
      });
      return this.flt(sum, this.currency_precision);
    },
    // Calculate subtotal after discounts and delivery charges
    subtotal() {
      this.close_payments();
      let sum = 0;
      this.items.forEach((item) => {
        // For returns, use absolute value for correct calculation
        const qty = this.invoiceType === "Return" ? Math.abs(flt(item.qty)) : flt(item.qty);
        const rate = flt(item.rate);
        sum += qty * rate;
      });
      // Subtract additional discount
      const additional_discount = this.flt(this.additional_discount);
      sum -= additional_discount;
      // Add delivery charges
      const delivery_charges = this.flt(this.delivery_charges_rate);
      sum += delivery_charges;
      return this.flt(sum, this.currency_precision);
    },
    // Calculate total discount amount for all items
    total_items_discount_amount() {
      let sum = 0;
      this.items.forEach((item) => {
        // For returns, use absolute value for correct calculation
        if (this.invoiceType === "Return") {
          sum += Math.abs(flt(item.qty)) * flt(item.discount_amount);
        } else {
          sum += flt(item.qty) * flt(item.discount_amount);
        }
      });
      return this.flt(sum, this.float_precision);
    },
    // Format posting_date for display as DD-MM-YYYY
    formatted_posting_date: {
      get() {
        if (!this.posting_date) return '';
        const parts = this.posting_date.split('-');
        if (parts.length === 3) {
          return `${parts[2]}-${parts[1]}-${parts[0]}`;
        }
        return this.posting_date;
      },
      set(val) {
        const parts = val.split('-');
        if (parts.length === 3) {
          this.posting_date = `${parts[2]}-${parts[1]}-${parts[0]}`;
        } else {
          this.posting_date = val;
        }
      }
    },
    // Get currency symbol for display
    currencySymbol() {
      return (currency) => {
        return get_currency_symbol(currency || this.selected_currency || this.pos_profile.currency);
      };
    },
    // Get display currency
    displayCurrency() {
      return this.selected_currency || this.pos_profile.currency;
    },
    // Table headers for item table (for another table if needed)
    itemTableHeaders() {
      return [
        {
          text: __('Item'),
          value: 'item_name',
          width: '35%',
        },
        {
          text: __('Qty'),
          value: 'qty',
          width: '15%',
        },
        {
          text: __(`Rate (${this.displayCurrency})`),
          value: 'rate',
          width: '20%',
        },
        {
          text: __(`Amount (${this.displayCurrency})`),
          value: 'amount',
          width: '20%',
        },
        {
          text: __('Action'),
          value: 'actions',
          sortable: false,
          width: '10%',
        },
      ];
    },
  },

  methods: {
    shortOpenFirstItem(e) {
      if (e.key.toLowerCase() === "a" && (e.ctrlKey || e.metaKey)) {
        try {
          e.preventDefault();
          e.stopPropagation();
          
          if (!this.items || this.items.length === 0) {
            console.log('No items to expand/collapse');
            return;
          }

          const firstItem = this.items[0];
          console.log('Processing first item:', firstItem.item_code);
          
          // Check if first item is currently expanded using its ID
          const isExpanded = this.expanded.includes(firstItem.posa_row_id);
          
          // Toggle expanded state using item ID
          if (isExpanded) {
            console.log('Collapsing item:', firstItem.item_code);
            this.expanded = [];
          } else {
            console.log('Expanding item:', firstItem.item_code);
            this.expanded = [firstItem.posa_row_id];
            // Update item details when expanding
            this.$nextTick(() => {
              this.update_item_detail(firstItem);
            });
          }
        } catch (error) {
          console.error('Error in shortOpenFirstItem:', error);
          this.eventBus.emit("show_message", {
            title: __("Error toggling item details"),
            color: "error"
          });
        }
      }
    },

    handleExpandedUpdate(newExpanded) {
      console.log('Expanded state updated:', newExpanded);
      this.expanded = newExpanded;
      
      // Update item details for newly expanded items
      if (newExpanded && newExpanded.length > 0) {
        const expandedItemId = newExpanded[0];
        const expandedItem = this.items.find(item => item.posa_row_id === expandedItemId);
        if (expandedItem) {
          this.$nextTick(() => {
            this.update_item_detail(expandedItem);
          });
        }
      }
    },

    remove_item(item) {
      const index = this.items.findIndex(
        (el) => el.posa_row_id == item.posa_row_id
      );
      if (index >= 0) {
        this.items.splice(index, 1);
      }
      // Remove from expanded if present
      this.expanded = this.expanded.filter(id => id !== item.posa_row_id);
    },

    add_item(item) {
      if (!item.uom) {
        item.uom = item.stock_uom;
      }
      let index = -1;
      if (!this.new_line) {
        index = this.items.findIndex(
          (el) =>
            el.item_code === item.item_code &&
            el.uom === item.uom &&
            !el.posa_is_offer &&
            !el.posa_is_replace &&
            ((el.batch_no && item.batch_no && el.batch_no === item.batch_no) || (!el.batch_no && !item.batch_no))
        );
      }

      let new_item;
      if (index === -1 || this.new_line) {
        new_item = this.get_new_item(item);
        // Handle serial number logic
        if (item.has_serial_no && item.to_set_serial_no) {
          new_item.serial_no_selected = [];
          new_item.serial_no_selected.push(item.to_set_serial_no);
          item.to_set_serial_no = null;
        }
        // Handle batch number logic
        if (item.has_batch_no && item.to_set_batch_no) {
          new_item.batch_no = item.to_set_batch_no;
          item.to_set_batch_no = null;
          item.batch_no = null;
          this.set_batch_qty(new_item, new_item.batch_no, false);
        }
        // Make quantity negative for returns
        if (this.invoiceType === "Return") {
          new_item.qty = -Math.abs(new_item.qty || 1);
        }
        this.items.unshift(new_item);
        this.update_item_detail(new_item);

        // Expand new item if it has batch or serial number
        if ((!this.pos_profile.posa_auto_set_batch && new_item.has_batch_no) || new_item.has_serial_no) {
          this.$nextTick(() => {
            this.expanded = [new_item.posa_row_id];
          });
        }
      } else {
        const cur_item = this.items[index];
        this.update_items_details([cur_item]);
        // Serial number logic for existing item
        if (item.has_serial_no && item.to_set_serial_no) {
          if (cur_item.serial_no_selected.includes(item.to_set_serial_no)) {
            this.eventBus.emit("show_message", {
              title: __(`This Serial Number {0} has already been added!`, [
                item.to_set_serial_no,
              ]),
              color: "warning",
            });
            item.to_set_serial_no = null;
            return;
          }
          cur_item.serial_no_selected.push(item.to_set_serial_no);
          item.to_set_serial_no = null;
        }
        
        // For returns, subtract from quantity to make it more negative
        if (this.invoiceType === "Return") {
          cur_item.qty -= (item.qty || 1);
        } else {
          cur_item.qty += (item.qty || 1);
        }
        this.calc_stock_qty(cur_item, cur_item.qty);
        
        // Update batch quantity if needed
        if (cur_item.has_batch_no && cur_item.batch_no) {
          this.set_batch_qty(cur_item, cur_item.batch_no, false);
        }
        
        this.set_serial_no(cur_item);
      }
      this.$forceUpdate();
      
      // Only try to expand if new_item exists and should be expanded
      if (new_item && ((!this.pos_profile.posa_auto_set_batch && new_item.has_batch_no) || new_item.has_serial_no)) {
        this.expanded = [new_item.posa_row_id];
      }
    },

    // Create a new item object with default and calculated fields
    get_new_item(item) {
      const new_item = { ...item };
      if (!item.qty) {
        item.qty = 1;
      }
      if (!item.posa_is_offer) {
        item.posa_is_offer = 0;
      }
      if (!item.posa_is_replace) {
        item.posa_is_replace = "";
      }

      // Set negative quantity for return invoices
      if (this.invoiceType === "Return" && item.qty > 0) {
        item.qty = -Math.abs(item.qty);
      }

      new_item.stock_qty = item.qty;
      new_item.discount_amount = 0;
      new_item.discount_percentage = 0;
      new_item.discount_amount_per_item = 0;
      new_item.price_list_rate = item.rate;
      new_item.base_price_list_rate = item.rate; // Add base_price_list_rate
      new_item.qty = item.qty;
      new_item.uom = item.uom ? item.uom : item.stock_uom;
      // Ensure item_uoms is initialized
      new_item.item_uoms = item.item_uoms || [];
      if (new_item.item_uoms.length === 0 && new_item.stock_uom) {
        new_item.item_uoms.push({ uom: new_item.stock_uom, conversion_factor: 1 });
      }
      new_item.actual_batch_qty = "";
      new_item.conversion_factor = 1;
      new_item.posa_offers = JSON.stringify([]);
      new_item.posa_offer_applied = 0;
      new_item.posa_is_offer = item.posa_is_offer;
      new_item.posa_is_replace = item.posa_is_replace || null;
      new_item.is_free_item = 0;
      new_item.posa_notes = "";
      new_item.posa_delivery_date = "";
      new_item.posa_row_id = this.makeid(20);
      // Expand row if batch/serial required
      if (
        (!this.pos_profile.posa_auto_set_batch && new_item.has_batch_no) ||
        new_item.has_serial_no
      ) {
        this.expanded.push(new_item);
      }
      return new_item;
    },

    // Reset all invoice fields to default/empty values
    clear_invoice() {
      this.items = [];
      this.posa_offers = [];
      this.expanded = [];
      this.eventBus.emit("set_pos_coupons", []);
      this.posa_coupons = [];
      this.invoice_doc = "";
      this.return_doc = "";
      this.discount_amount = 0;
      this.additional_discount = 0;  // Added for additional discount
      this.additional_discount_percentage = 0;
      this.delivery_charges_rate = 0;
      this.selected_delivery_charge = "";
      // Reset posting date to today
      this.posting_date = frappe.datetime.nowdate();

      // Always reset to default customer after invoice
      this.customer = this.pos_profile.customer;

      this.eventBus.emit("set_customer_readonly", false);
      this.invoiceType = this.pos_profile.posa_default_sales_order ? "Order" : "Invoice";
      this.invoiceTypes = ["Invoice", "Order"];
    },

    // Fetch customer balance from backend
    async fetch_customer_balance() {
      try {
        if (!this.customer) {
          this.customer_balance = 0;
          return;
        }
        const r = await frappe.call({
          method: "posawesome.posawesome.api.customer.get_customer_balance",
          args: { customer: this.customer }
        });
        this.customer_balance = r?.message?.balance || 0;

      } catch (error) {
        console.error("Error fetching balance:", error);
        this.eventBus.emit("show_message", {
          title: __("Error fetching customer balance"),
          color: "error"
        });
        this.customer_balance = 0;
      }
    },

    // Cancel the current invoice, optionally delete from backend
    async cancel_invoice() {
      const doc = this.get_invoice_doc();
      this.invoiceType = this.pos_profile.posa_default_sales_order
        ? "Order"
        : "Invoice";
      this.invoiceTypes = ["Invoice", "Order"];
      this.posting_date = frappe.datetime.nowdate();
      var vm = this;
      if (doc.name && this.pos_profile.posa_allow_delete) {
        await frappe.call({
          method: "posawesome.posawesome.api.posapp.delete_invoice",
          args: { invoice: doc.name },
          async: true,
          callback: function (r) {
            if (r.message) {
              vm.eventBus.emit("show_message", {
                text: r.message,
                color: "warning",
              });
            }
          },
        });
      }
      this.clear_invoice()
      this.cancel_dialog = false;
    },

    // Load an invoice (or return invoice) from data, set all fields accordingly
    async load_invoice(data = {}) {
      console.log("load_invoice called with data:", {
        is_return: data.is_return,
        return_against: data.return_against,
        customer: data.customer,
        items_count: data.items ? data.items.length : 0
      });
      
      this.clear_invoice()
      if (data.is_return) {
        console.log("Processing return invoice");
        // For return without invoice case, check if there's a return_against
        // Only set customer readonly if this is a return with reference to an invoice
        if (data.return_against) {
          console.log("Return has reference to invoice:", data.return_against);
          this.eventBus.emit("set_customer_readonly", true);
        } else {
          console.log("Return without invoice reference, customer can be selected");
          // Allow customer selection for returns without invoice
          this.eventBus.emit("set_customer_readonly", false);
        }
        this.invoiceType = "Return";
        this.invoiceTypes = ["Return"];
      }
      
      this.invoice_doc = data;
      this.items = data.items || [];
      console.log("Items set:", this.items.length, "items");
      
      if (this.items.length > 0) {
        this.update_items_details(this.items);
        this.posa_offers = data.posa_offers || [];
        this.items.forEach((item) => {
          if (!item.posa_row_id) {
            item.posa_row_id = this.makeid(20);
          }
          if (item.batch_no) {
            this.set_batch_qty(item, item.batch_no);
          }
        });
      } else {
        console.log("Warning: No items in return invoice");
      }
      
      this.customer = data.customer;
      this.posting_date = data.posting_date || frappe.datetime.nowdate();
      this.discount_amount = data.discount_amount;
      this.additional_discount_percentage =
        data.additional_discount_percentage;
        
      if (this.items.length > 0) {
        this.items.forEach((item) => {
          if (item.serial_no) {
            item.serial_no_selected = [];
            const serial_list = item.serial_no.split("\n");
            serial_list.forEach((element) => {
              if (element.length) {
                item.serial_no_selected.push(element);
              }
            });
            item.serial_no_selected_count = item.serial_no_selected.length;
          }
        });
      }
      
      if (data.is_return) {
        console.log("Setting return values for discounts");
        this.discount_amount = -data.discount_amount;
        this.additional_discount_percentage =
          -data.additional_discount_percentage;
        this.return_doc = data;
      } else {
        this.eventBus.emit("set_pos_coupons", data.posa_coupons);
      }
      
      console.log("load_invoice completed, invoice state:", {
        invoiceType: this.invoiceType,
        is_return: this.invoice_doc.is_return,
        items: this.items.length,
        customer: this.customer
      });
    },

    // Save and clear the current invoice (draft logic)
    save_and_clear_invoice() {
      const doc = this.get_invoice_doc();
      if (doc.name) {
        old_invoice = this.update_invoice(doc);
      } else {
        if (doc.items.length) {
          old_invoice = this.update_invoice(doc);
        }
        else {
          this.eventBus.emit("show_message", {
            title: `Nothing to save`,
            color: "error",
          });
        }
      }
      if (!old_invoice) {
        this.eventBus.emit("show_message", {
          title: `Error saving the current invoice`,
          color: "error",
        });
      }
      else {
        this.clear_invoice();
        return old_invoice;
      }

    },

    // Start a new order (or return order) with provided data
    async new_order(data = {}) {
      let old_invoice = null;
      this.eventBus.emit("set_customer_readonly", false);
      this.expanded = [];
      this.posa_offers = [];
      this.eventBus.emit("set_pos_coupons", []);
      this.posa_coupons = [];
      this.return_doc = "";
      if (!data.name && !data.is_return) {
        this.items = [];
        this.customer = this.pos_profile.customer;
        this.invoice_doc = "";
        this.discount_amount = 0;
        this.additional_discount_percentage = 0;
        this.invoiceType = "Invoice";
        this.invoiceTypes = ["Invoice", "Order"];
      } else {
        if (data.is_return) {
          // For return without invoice case, check if there's a return_against
          // Only set customer readonly if this is a return with reference to an invoice
          if (data.return_against) {
            this.eventBus.emit("set_customer_readonly", true);
          } else {
            // Allow customer selection for returns without invoice
            this.eventBus.emit("set_customer_readonly", false);
          }
          this.invoiceType = "Return";
          this.invoiceTypes = ["Return"];
        }
        this.invoice_doc = data;
        this.items = data.items;
        this.update_items_details(this.items);
        this.posa_offers = data.posa_offers || [];
        this.items.forEach((item) => {
          if (!item.posa_row_id) {
            item.posa_row_id = this.makeid(20);
          }
          if (item.batch_no) {
            this.set_batch_qty(item, item.batch_no);
          }
        });
        this.customer = data.customer;
        this.posting_date = data.posting_date || frappe.datetime.nowdate();
        this.discount_amount = data.discount_amount;
        this.additional_discount_percentage =
          data.additional_discount_percentage;
        this.items.forEach((item) => {
          if (item.serial_no) {
            item.serial_no_selected = [];
            const serial_list = item.serial_no.split("\n");
            serial_list.forEach((element) => {
              if (element.length) {
                item.serial_no_selected.push(element);
              }
            });
            item.serial_no_selected_count = item.serial_no_selected.length;
          }
        });
      }
      return old_invoice;
    },

    // Build the invoice document object for backend submission
    get_invoice_doc() {
      let doc = {};
      if (this.invoice_doc.name) {
        doc = { ...this.invoice_doc };
      }
      
      // Always set these fields first
      doc.doctype = "Sales Invoice";
      doc.is_pos = 1;
      doc.ignore_pricing_rule = 1;
      doc.company = doc.company || this.pos_profile.company;
      doc.pos_profile = doc.pos_profile || this.pos_profile.name;
      
      // Currency related fields
      doc.currency = this.selected_currency || this.pos_profile.currency;
      doc.conversion_rate = this.exchange_rate || 1;
      doc.plc_conversion_rate = this.exchange_rate || 1;
      doc.price_list_currency = doc.currency;
      
      // Other fields
      doc.campaign = doc.campaign || this.pos_profile.campaign;
      doc.selling_price_list = this.pos_profile.selling_price_list;
      doc.naming_series = doc.naming_series || this.pos_profile.naming_series;
      doc.customer = this.customer;
      
      // Determine if this is a return invoice
      const isReturn = this.invoiceType === 'Return' || this.invoice_doc.is_return;
      doc.is_return = isReturn ? 1 : 0;
      
      // Calculate amounts in selected currency
      const items = this.get_invoice_items();
      doc.items = items;
      
      // Calculate totals in selected currency ensuring negative values for returns
      let total = this.Total;
      if (isReturn && total > 0) total = -Math.abs(total);
      
      doc.total = total;
      doc.net_total = total;  // Net total is same as total before taxes
      doc.base_total = total * (1 / this.exchange_rate || 1);
      doc.base_net_total = total * (1 / this.exchange_rate || 1);
      
      // Apply discounts with correct sign for returns
      let discountAmount = flt(this.additional_discount);
      if (isReturn && discountAmount > 0) discountAmount = -Math.abs(discountAmount);
      
      doc.discount_amount = discountAmount;
      doc.base_discount_amount = discountAmount * (1 / this.exchange_rate || 1);
      
      let discountPercentage = flt(this.additional_discount_percentage);
      if (isReturn && discountPercentage > 0) discountPercentage = -Math.abs(discountPercentage);
      
      doc.additional_discount_percentage = discountPercentage;
      
      // Calculate grand total with correct sign for returns
      let grandTotal = this.subtotal;
      if (isReturn && grandTotal > 0) grandTotal = -Math.abs(grandTotal);
      
      doc.grand_total = grandTotal;
      doc.base_grand_total = grandTotal * (1 / this.exchange_rate || 1);
      
      // Apply rounding to get rounded total
      doc.rounded_total = this.roundAmount(grandTotal);
      doc.base_rounded_total = this.roundAmount(doc.base_grand_total);
      
      // Add POS specific fields
      doc.posa_pos_opening_shift = this.pos_opening_shift.name;
      doc.payments = this.get_payments();
      doc.taxes = [];
      
      // Handle return specific fields
      if (isReturn) {
        if (this.invoice_doc.return_against) {
          doc.return_against = this.invoice_doc.return_against;
        }
        doc.update_stock = 1;
        
        // Double-check all values are negative
        if (doc.grand_total > 0) doc.grand_total = -Math.abs(doc.grand_total);
        if (doc.base_grand_total > 0) doc.base_grand_total = -Math.abs(doc.base_grand_total);
        if (doc.rounded_total > 0) doc.rounded_total = -Math.abs(doc.rounded_total);
        if (doc.base_rounded_total > 0) doc.base_rounded_total = -Math.abs(doc.base_rounded_total);
        if (doc.total > 0) doc.total = -Math.abs(doc.total);
        if (doc.base_total > 0) doc.base_total = -Math.abs(doc.base_total);
        if (doc.net_total > 0) doc.net_total = -Math.abs(doc.net_total);
        if (doc.base_net_total > 0) doc.base_net_total = -Math.abs(doc.base_net_total);
        
        // Ensure payments have negative amounts
        if (doc.payments && doc.payments.length) {
          doc.payments.forEach(payment => {
            if (payment.amount > 0) payment.amount = -Math.abs(payment.amount);
            if (payment.base_amount > 0) payment.base_amount = -Math.abs(payment.base_amount);
          });
        }
      }
      
      // Add offer details
      doc.posa_offers = this.posa_offers;
      doc.posa_coupons = this.posa_coupons;
      doc.posa_delivery_charges = this.selected_delivery_charge.name;
      doc.posa_delivery_charges_rate = this.delivery_charges_rate || 0;
      doc.posting_date = this.posting_date;
      
      // Add flags to ensure proper rate handling
      doc.ignore_pricing_rule = 1;
      doc.price_list_currency = doc.currency;
      doc.plc_conversion_rate = doc.conversion_rate;
      doc.ignore_default_fields = 1;  // Add this to prevent default field updates
      
      // Add custom fields to track offer rates
      doc.posa_is_offer_applied = this.posa_offers.length > 0 ? 1 : 0;
      
      // Calculate base amounts using the exchange rate
      if (this.selected_currency !== this.pos_profile.currency) {
        // For returns, we need to ensure negative values
        const multiplier = isReturn ? -1 : 1;
        
        // If exchange rate is 300 PKR = 1 USD
        // To convert USD to PKR: multiply by exchange rate
        doc.base_total = total * this.exchange_rate * multiplier;
        doc.base_net_total = total * this.exchange_rate * multiplier;
        doc.base_discount_amount = discountAmount * this.exchange_rate * multiplier;
        doc.base_grand_total = grandTotal * this.exchange_rate * multiplier;
        doc.base_rounded_total = grandTotal * this.exchange_rate * multiplier;
      } else {
        // Same currency, just ensure negative values for returns
        const multiplier = isReturn ? -1 : 1;
        doc.base_total = total * multiplier;
        doc.base_net_total = total * multiplier;
        doc.base_discount_amount = discountAmount * multiplier;
        doc.base_grand_total = grandTotal * multiplier;
        doc.base_rounded_total = grandTotal * multiplier;
      }
      
      // Ensure payments have correct base amounts
      if (doc.payments && doc.payments.length) {
        doc.payments.forEach(payment => {
          if (this.selected_currency !== this.pos_profile.currency) {
            // Convert payment amount to base currency
            payment.base_amount = payment.amount * this.exchange_rate;
          } else {
            payment.base_amount = payment.amount;
          }
          
          // For returns, ensure negative values
          if (isReturn) {
            payment.amount = -Math.abs(payment.amount);
            payment.base_amount = -Math.abs(payment.base_amount);
          }
        });
      }
      
      return doc;
    },

    // Get invoice doc from order doc (for sales order to invoice conversion)
    async get_invoice_from_order_doc() {
      let doc = {};
      if (this.invoice_doc.doctype == "Sales Order") {
        await frappe.call({
          method:
            "posawesome.posawesome.api.posapp.create_sales_invoice_from_order",
          args: {
            sales_order: this.invoice_doc.name,
          },
          // async: false,
          callback: function (r) {
            if (r.message) {
              doc = r.message;
            }
          },
        });
      } else {
        doc = this.invoice_doc;
      }
      const Items = [];
      const updatedItemsData = this.get_invoice_items();
      doc.items.forEach((item) => {
        const updatedData = updatedItemsData.find(
          (updatedItem) => updatedItem.item_code === item.item_code
        );
        if (updatedData) {
          item.item_code = updatedData.item_code;
          item.posa_row_id = updatedData.posa_row_id;
          item.posa_offers = updatedData.posa_offers;
          item.posa_offer_applied = updatedData.posa_offer_applied;
          item.posa_is_offer = updatedData.posa_is_offer;
          item.posa_is_replace = updatedData.posa_is_replace;
          item.is_free_item = updatedData.is_free_item;
          item.qty = flt(updatedData.qty);
          item.rate = flt(updatedData.rate);
          item.uom = updatedData.uom;
          item.amount = flt(updatedData.qty) * flt(updatedData.rate);
          item.conversion_factor = updatedData.conversion_factor;
          item.serial_no = updatedData.serial_no;
          item.discount_percentage = flt(updatedData.discount_percentage);
          item.discount_amount = flt(updatedData.discount_amount);
          item.batch_no = updatedData.batch_no;
          item.posa_notes = updatedData.posa_notes;
          item.posa_delivery_date = updatedData.posa_delivery_date;
          item.price_list_rate = updatedData.price_list_rate;
          Items.push(item);
        }
      });

      doc.items = Items;
      const newItems = [...doc.items];
      const existingItemCodes = new Set(newItems.map((item) => item.item_code));
      updatedItemsData.forEach((updatedItem) => {
        if (!existingItemCodes.has(updatedItem.item_code)) {
          newItems.push(updatedItem);
        }
      });
      doc.items = newItems;
      doc.update_stock = 1;
      doc.is_pos = 1;
      doc.payments = this.get_payments();
      return doc;
    },

    // Prepare items array for invoice doc
    get_invoice_items() {
      const items_list = [];
      const isReturn = this.invoiceType === 'Return' || this.invoice_doc.is_return;
      
      this.items.forEach((item) => {
        const new_item = {
          item_code: item.item_code,
          posa_row_id: item.posa_row_id,
          posa_offers: item.posa_offers,
          posa_offer_applied: item.posa_offer_applied,
          posa_is_offer: item.posa_is_offer,
          posa_is_replace: item.posa_is_replace,
          is_free_item: item.is_free_item,
          qty: flt(item.qty),
          uom: item.uom,
          conversion_factor: item.conversion_factor,
          serial_no: item.serial_no,
          discount_percentage: flt(item.discount_percentage),
          batch_no: item.batch_no,
          posa_notes: item.posa_notes,
          posa_delivery_date: item.posa_delivery_date,
        };

        // Handle currency conversion for rates and amounts
        if (this.selected_currency !== this.pos_profile.currency) {
          // If exchange rate is 300 PKR = 1 USD
          // item.rate is in USD (e.g. 10 USD)
          // base_rate should be in PKR (e.g. 3000 PKR)
          new_item.rate = flt(item.rate);  // Keep rate in USD
          new_item.base_rate = flt(item.rate * this.exchange_rate);  // Convert to PKR
          
          new_item.price_list_rate = flt(item.price_list_rate);  // Keep price list rate in USD
          new_item.base_price_list_rate = flt(item.price_list_rate * this.exchange_rate);  // Convert to PKR
          
          // Calculate amounts
          new_item.amount = flt(item.qty) * new_item.rate;  // Amount in USD
          new_item.base_amount = new_item.amount * this.exchange_rate;  // Convert to PKR
          
          // Handle discount amount
          new_item.discount_amount = flt(item.discount_amount);  // Keep discount in USD
          new_item.base_discount_amount = flt(item.discount_amount * this.exchange_rate);  // Convert to PKR
        } else {
          // Same currency (PKR), no conversion needed
          new_item.rate = flt(item.rate);
          new_item.base_rate = flt(item.rate);
          new_item.price_list_rate = flt(item.price_list_rate);
          new_item.base_price_list_rate = flt(item.price_list_rate);
          new_item.amount = flt(item.qty) * new_item.rate;
          new_item.base_amount = new_item.amount;
          new_item.discount_amount = flt(item.discount_amount);
          new_item.base_discount_amount = flt(item.discount_amount);
        }

        // For returns, ensure all amounts are negative
        if (isReturn) {
          new_item.qty = -Math.abs(new_item.qty);
          new_item.amount = -Math.abs(new_item.amount);
          new_item.base_amount = -Math.abs(new_item.base_amount);
          new_item.discount_amount = -Math.abs(new_item.discount_amount);
          new_item.base_discount_amount = -Math.abs(new_item.base_discount_amount);
        }

        items_list.push(new_item);
      });
      
      return items_list;
    },

    // Prepare items array for order doc
    get_order_items() {
      const items_list = [];
      this.items.forEach((item) => {
        const new_item = {
          item_code: item.item_code,
          posa_row_id: item.posa_row_id,
          posa_offers: item.posa_offers,
          posa_offer_applied: item.posa_offer_applied,
          posa_is_offer: item.posa_is_offer,
          posa_is_replace: item.posa_is_replace,
          is_free_item: item.is_free_item,
          qty: flt(item.qty),
          rate: flt(item.rate),
          uom: item.uom,
          amount: flt(item.qty) * flt(item.rate),
          conversion_factor: item.conversion_factor,
          serial_no: item.serial_no,
          discount_percentage: flt(item.discount_percentage),
          discount_amount: flt(item.discount_amount),
          batch_no: item.batch_no,
          posa_notes: item.posa_notes,
          posa_delivery_date: item.posa_delivery_date,
          price_list_rate: item.price_list_rate,
        };
        items_list.push(new_item);
      });

      return items_list;
    },

    // Prepare payments array for invoice doc
    get_payments() {
      const payments = [];
      // Use this.subtotal which is already in selected currency and includes all calculations
      const total_amount = this.subtotal;
      let remaining_amount = total_amount;
      
      this.pos_profile.payments.forEach((payment, index) => {
        // For the first payment method, assign the full remaining amount
        const payment_amount = index === 0 ? remaining_amount : (payment.amount || 0);
        
        // For return invoices, ensure payment amounts are negative
        const adjusted_amount = this.invoiceType === 'Return' || this.invoice_doc.is_return ? 
          -Math.abs(payment_amount) : payment_amount;
        
        // Handle currency conversion
        // If selected_currency is USD and base is PKR:
        // amount is in USD (e.g. 10 USD)
        // base_amount should be in PKR (e.g. 3000 PKR)
        // So multiply by exchange rate to get base_amount
        const base_amount = this.selected_currency !== this.pos_profile.currency ? 
          this.flt(adjusted_amount * (this.exchange_rate || 1), this.currency_precision) : 
          adjusted_amount;
        
        payments.push({
          amount: adjusted_amount,  // Keep in selected currency (e.g. USD)
          base_amount: base_amount,  // Convert to base currency (e.g. PKR)
          mode_of_payment: payment.mode_of_payment,
          default: payment.default,
          account: payment.account || "",
          type: payment.type || "Cash",
          currency: this.selected_currency || this.pos_profile.currency,
          conversion_rate: this.exchange_rate || 1
        });

        remaining_amount -= payment_amount;
      });

      console.log('Generated payments:', {
        currency: this.selected_currency,
        exchange_rate: this.exchange_rate,
        payments: payments.map(p => ({
          mode: p.mode_of_payment,
          amount: p.amount,
          base_amount: p.base_amount
        }))
      });
      
      return payments;
    },

    // Convert amount to selected currency
    convert_amount(amount) {
      if (this.selected_currency === this.pos_profile.currency) {
        return amount;
      }
      return this.flt(amount * this.exchange_rate, this.currency_precision);
    },

    // Update invoice in backend
    update_invoice(doc) {
      var vm = this;
      frappe.call({
        method: "posawesome.posawesome.api.posapp.update_invoice",
        args: {
          data: doc,
        },
        async: false,
        callback: function (r) {
          if (r.message) {
            vm.invoice_doc = r.message;
          }
        },
      });
      return this.invoice_doc;
    },

    // Update invoice from order in backend
    update_invoice_from_order(doc) {
      var vm = this;
      frappe.call({
        method: "posawesome.posawesome.api.posapp.update_invoice_from_order",
        args: {
          data: doc,
        },
        async: false,
        callback: function (r) {
          if (r.message) {
            vm.invoice_doc = r.message;
          }
        },
      });
      return this.invoice_doc;
    },

    // Process and save invoice (handles update or create)
    process_invoice() {
      const doc = this.get_invoice_doc();
      if (doc.name) {
        try {
          const updated_doc = this.update_invoice(doc);
          // Update posting date after invoice update
          if (updated_doc && updated_doc.posting_date) {
            this.posting_date = updated_doc.posting_date;
          }
          return updated_doc;
        } catch (error) {
          console.error('Error in process_invoice:', error);
          this.eventBus.emit('show_message', {
            title: __(error.message || 'Error processing invoice'),
            color: 'error'
          });
          return false;
        }
      } else {
        try {
          const updated_doc = this.update_invoice(doc);
          // Update posting date after invoice creation
          if (updated_doc && updated_doc.posting_date) {
            this.posting_date = updated_doc.posting_date;
          }
          return updated_doc;
        } catch (error) {
          console.error('Error in process_invoice:', error);
          this.eventBus.emit('show_message', {
            title: __(error.message || 'Error processing invoice'),
            color: 'error'
          });
          return false;
        }
      }
    },

    // Process and save invoice from order
    async process_invoice_from_order() {
      const doc = await this.get_invoice_from_order_doc();
      var up_invoice;
      if (doc.name) {
        up_invoice = await this.update_invoice_from_order(doc);
        return up_invoice;
      } else {
        return this.update_invoice_from_order(doc);
      }
    },

    // Show payment dialog after validation and processing
    async show_payment() {
      try {
        console.log('Starting show_payment process');
        console.log('Invoice state before payment:', {
          invoiceType: this.invoiceType,
          is_return: this.invoice_doc ? this.invoice_doc.is_return : false,
          items_count: this.items.length,
          customer: this.customer
        });

        if (!this.customer) {
          console.log('Customer validation failed');
          this.eventBus.emit("show_message", {
            title: __(`Select a customer`),
            color: "error",
          });
          return;
        }

        if (!this.items.length) {
          console.log('Items validation failed - no items');
          this.eventBus.emit("show_message", {
            title: __(`Select items to sell`),
            color: "error",
          });
          return;
        }

        console.log('Basic validations passed, proceeding to main validation');
        const isValid = this.validate();
        console.log('Main validation result:', isValid);

        if (!isValid) {
          console.log('Main validation failed');
          return;
        }

        let invoice_doc;
        if (this.invoice_doc.doctype == "Sales Order") {
          console.log('Processing Sales Order payment');
          invoice_doc = await this.process_invoice_from_order();
        } else {
          console.log('Processing regular invoice');
          invoice_doc = this.process_invoice();
        }

        if (!invoice_doc) {
          console.log('Failed to process invoice');
          return;
        }

        // Update invoice_doc with current currency info
        invoice_doc.currency = this.selected_currency || this.pos_profile.currency;
        invoice_doc.conversion_rate = this.exchange_rate || 1;
        
        // Update totals in invoice_doc to match current calculations
        invoice_doc.total = this.Total;
        invoice_doc.grand_total = this.subtotal;
        
        // Apply rounding to get rounded total
        invoice_doc.rounded_total = this.roundAmount(this.subtotal);
        invoice_doc.base_total = this.Total * (1 / this.exchange_rate || 1);
        invoice_doc.base_grand_total = this.subtotal * (1 / this.exchange_rate || 1);
        invoice_doc.base_rounded_total = this.roundAmount(invoice_doc.base_grand_total);
        
        // Check if this is a return invoice
        if (this.invoiceType === 'Return' || invoice_doc.is_return) {
          console.log('Preparing RETURN invoice for payment with:', {
            is_return: invoice_doc.is_return,
            invoiceType: this.invoiceType,
            return_against: invoice_doc.return_against,
            items: invoice_doc.items.length,
            grand_total: invoice_doc.grand_total
          });
          
          // For return invoices, explicitly ensure all amounts are negative
          invoice_doc.is_return = 1;
          if (invoice_doc.grand_total > 0) invoice_doc.grand_total = -Math.abs(invoice_doc.grand_total);
          if (invoice_doc.rounded_total > 0) invoice_doc.rounded_total = -Math.abs(invoice_doc.rounded_total);
          if (invoice_doc.total > 0) invoice_doc.total = -Math.abs(invoice_doc.total);
          if (invoice_doc.base_grand_total > 0) invoice_doc.base_grand_total = -Math.abs(invoice_doc.base_grand_total);
          if (invoice_doc.base_rounded_total > 0) invoice_doc.base_rounded_total = -Math.abs(invoice_doc.base_rounded_total);
          if (invoice_doc.base_total > 0) invoice_doc.base_total = -Math.abs(invoice_doc.base_total);
          
          // Ensure all items have negative quantity and amount
          if (invoice_doc.items && invoice_doc.items.length) {
            invoice_doc.items.forEach(item => {
              if (item.qty > 0) item.qty = -Math.abs(item.qty);
              if (item.stock_qty > 0) item.stock_qty = -Math.abs(item.stock_qty);
              if (item.amount > 0) item.amount = -Math.abs(item.amount);
            });
          }
        }
        
        // Get payments with correct sign (positive/negative)
        invoice_doc.payments = this.get_payments();
        console.log('Final payment data:', invoice_doc.payments);

        // Double-check return invoice payments are negative
        if ((this.invoiceType === 'Return' || invoice_doc.is_return) && invoice_doc.payments.length) {
          invoice_doc.payments.forEach(payment => {
            if (payment.amount > 0) payment.amount = -Math.abs(payment.amount);
            if (payment.base_amount > 0) payment.base_amount = -Math.abs(payment.base_amount);
          });
          console.log('Ensured negative payment amounts for return:', invoice_doc.payments);
        }

        console.log('Showing payment dialog with currency:', invoice_doc.currency);
        this.eventBus.emit("show_payment", "true");
        this.eventBus.emit("send_invoice_doc_payment", invoice_doc);

      } catch (error) {
        console.error('Error in show_payment:', error);
        this.eventBus.emit("show_message", {
          title: __("Error processing payment"),
          color: "error",
          message: error.message
        });
      }
    },

    // Validate invoice before payment/submit (return logic, quantity, rates, etc)
    async validate() {
      console.log('Starting return validation');
      
      // For all returns, check if amounts are negative
      if (this.invoiceType === 'Return' || this.invoice_doc.is_return) {
        console.log('Validating return invoice values');
        
        // Check if quantities are negative
        const positiveItems = this.items.filter(item => item.qty >= 0 || item.stock_qty >= 0);
        if (positiveItems.length > 0) {
          console.log('Found positive quantities in return items:', positiveItems.map(i => i.item_code));
          this.eventBus.emit('show_message', {
            title: __(`Return items must have negative quantities`),
            color: 'error'
          });
          
          // Fix the quantities to be negative
          positiveItems.forEach(item => {
            item.qty = -Math.abs(item.qty);
            item.stock_qty = -Math.abs(item.stock_qty);
          });
          
          // Force update to reflect changes
          this.$forceUpdate();
        }
        
        // Ensure total amount is negative
        if (this.subtotal > 0) {
          console.log('Return has positive subtotal:', this.subtotal);
          this.eventBus.emit('show_message', {
            title: __(`Return total must be negative`),
            color: 'warning'
          });
        }
      }
      
      // For return with reference to existing invoice
      if (this.invoice_doc.is_return && this.invoice_doc.return_against) {
        console.log('Return doc:', this.invoice_doc);
        console.log('Current items:', this.items);

        try {
          // Get original invoice items for comparison
          const original_items = await new Promise((resolve, reject) => {
            frappe.call({
              method: 'frappe.client.get',
              args: {
                doctype: 'Sales Invoice',
                name: this.invoice_doc.return_against
              },
              callback: (r) => {
                if (r.message) {
                  console.log('Original invoice data:', r.message);
                  resolve(r.message.items || []);
                } else {
                  reject(new Error('Original invoice not found'));
                }
              }
            });
          });

          console.log('Original invoice items:', original_items);
          console.log('Original item codes:', original_items.map(item => ({
            item_code: item.item_code,
            qty: item.qty,
            rate: item.rate
          })));

          // Validate each return item
          for (const item of this.items) {
            console.log('Validating return item:', {
              item_code: item.item_code,
              rate: item.rate,
              qty: item.qty
            });

            // Normalize item codes by trimming and converting to uppercase
            const normalized_return_item_code = item.item_code.trim().toUpperCase();

            // Find matching item in original invoice
            const original_item = original_items.find(orig =>
              orig.item_code.trim().toUpperCase() === normalized_return_item_code
            );

            if (!original_item) {
              console.log('Item not found in original invoice:', {
                return_item_code: normalized_return_item_code,
                original_items: original_items.map(i => i.item_code.trim().toUpperCase())
              });

              this.eventBus.emit('show_message', {
                title: __(`Item ${item.item_code} not found in original invoice`),
                color: 'error'
              });
              return false;
            }

            // Compare rates with precision
            const rate_diff = Math.abs(original_item.rate - item.rate);
            console.log('Rate comparison:', {
              return_rate: item.rate,
              orig_rate: original_item.rate,
              difference: rate_diff
            });

            if (rate_diff > 0.01) {
              this.eventBus.emit('show_message', {
                title: __(`Rate mismatch for item ${item.item_code}`),
                color: 'error'
              });
              return false;
            }

            // Compare quantities
            const return_qty = Math.abs(item.qty);
            const orig_qty = original_item.qty;
            console.log('Quantity comparison:', {
              return_qty: return_qty,
              orig_qty: orig_qty
            });

            if (return_qty > orig_qty) {
              this.eventBus.emit('show_message', {
                title: __(`Return quantity cannot be greater than original quantity for item ${item.item_code}`),
                color: 'error'
              });
              return false;
            }
          }
        } catch (error) {
          console.error('Error in validation:', error);
          this.eventBus.emit('show_message', {
            title: __(`Error validating return: ${error.message}`),
            color: 'error'
          });
          return false;
        }
      }
      return true;
    },

    // Get draft invoices from backend
    get_draft_invoices() {
      var vm = this;
      frappe.call({
        method: "posawesome.posawesome.api.posapp.get_draft_invoices",
        args: {
          pos_opening_shift: this.pos_opening_shift.name,
        },
        async: false,
        callback: function (r) {
          if (r.message) {
            vm.eventBus.emit("open_drafts", r.message);
          }
        },
      });
    },

    // Get draft orders from backend
    get_draft_orders() {
      var vm = this;
      frappe.call({
        method: "posawesome.posawesome.api.posapp.search_orders",
        args: {
          company: this.pos_profile.company,
          currency: this.pos_profile.currency,
        },
        async: false,
        callback: function (r) {
          if (r.message) {
            vm.eventBus.emit("open_orders", r.message);
          }
        },
      });
    },

    // Open returns dialog
    open_returns() {
      this.eventBus.emit("open_returns", this.pos_profile.company);
    },

    // Close payment dialog
    close_payments() {
      this.eventBus.emit("show_payment", "false");
    },

    // Update details for all items (fetch from backend)
    async update_items_details(items) {
      if (!items?.length) return;
      if (!this.pos_profile) return;

      try {
        const response = await frappe.call({
          method: "posawesome.posawesome.api.posapp.get_items_details",
          args: {
            pos_profile: this.pos_profile,
            items_data: items
          }
        });

        if (response?.message) {
          items.forEach((item) => {
            const updated_item = response.message.find(
              (element) => element.posa_row_id == item.posa_row_id
            );
            if (updated_item) {
              item.actual_qty = updated_item.actual_qty;
              item.serial_no_data = updated_item.serial_no_data;
              item.batch_no_data = updated_item.batch_no_data;
              item.item_uoms = updated_item.item_uoms;
              item.has_batch_no = updated_item.has_batch_no;
              item.has_serial_no = updated_item.has_serial_no;
            }
          });
        }
      } catch (error) {
        console.error("Error updating items:", error);
        this.eventBus.emit("show_message", {
          title: __("Error updating item details"),
          color: "error"
        });
      }
    },

    // Update details for a single item (fetch from backend)
    update_item_detail(item) {
      if (!item.item_code) {
        return;
      }
      var vm = this;
      
      // Only update rate if no offer is applied
      if (item.price_list_rate && !item.posa_offer_applied) {
        item.rate = item.price_list_rate;
        this.$forceUpdate();
      }

      frappe.call({
        method: "posawesome.posawesome.api.posapp.get_item_detail",
        args: {
          warehouse: this.pos_profile.warehouse,
          doc: this.get_invoice_doc(),
          price_list: this.pos_profile.price_list,
          item: {
            item_code: item.item_code,
            customer: this.customer,
            doctype: "Sales Invoice",
            name: "New Sales Invoice 1",
            company: this.pos_profile.company,
            conversion_rate: 1,
            currency: this.pos_profile.currency,
            qty: item.qty,
            price_list_rate: item.base_price_list_rate || item.price_list_rate,
            child_docname: "New Sales Invoice Item 1",
            cost_center: this.pos_profile.cost_center,
            pos_profile: this.pos_profile.name,
            uom: item.uom,
            tax_category: "",
            transaction_type: "selling",
            update_stock: this.pos_profile.update_stock,
            price_list: this.get_price_list(),
            has_batch_no: item.has_batch_no,
            serial_no: item.serial_no,
            batch_no: item.batch_no,
            is_stock_item: item.is_stock_item,
          },
        },
        callback: function (r) {
          if (r.message) {
            const data = r.message;
            if (data.batch_no_data) {
              item.batch_no_data = data.batch_no_data;
            }
            if (
              item.has_batch_no &&
              vm.pos_profile.posa_auto_set_batch &&
              !item.batch_no &&
              data.batch_no_data
            ) {
              item.batch_no_data = data.batch_no_data;
              vm.set_batch_qty(item, item.batch_no, false);
            }
            
            // Always store base rates from server
            item.base_price_list_rate = data.price_list_rate;
            
            // Only update rates if no offer is applied
            if (!item.posa_offer_applied) {
              item.base_rate = data.price_list_rate;
              
              // Convert to selected currency if needed
              if (vm.selected_currency !== vm.pos_profile.currency) {
                const exchange_rate = vm.exchange_rate || 1;
                item.price_list_rate = vm.flt(data.price_list_rate / exchange_rate, vm.currency_precision);
                item.rate = vm.flt(data.price_list_rate / exchange_rate, vm.currency_precision);
              } else {
                item.price_list_rate = data.price_list_rate;
                item.rate = data.price_list_rate;
              }
            } else {
              // For items with offers, only update price_list_rate
              if (vm.selected_currency !== vm.pos_profile.currency) {
                const exchange_rate = vm.exchange_rate || 1;
                item.price_list_rate = vm.flt(data.price_list_rate / exchange_rate, vm.currency_precision);
              } else {
                item.price_list_rate = data.price_list_rate;
              }
            }

            // Handle customer discount only if no offer is applied
            if (
              !item.posa_offer_applied &&
              vm.pos_profile.posa_apply_customer_discount &&
              vm.customer_info.posa_discount > 0 &&
              vm.customer_info.posa_discount <= 100 &&
              item.posa_is_offer == 0 &&
              !item.posa_is_replace
            ) {
              const discount_percent = item.max_discount > 0 
                ? Math.min(item.max_discount, vm.customer_info.posa_discount)
                : vm.customer_info.posa_discount;
              
              item.discount_percentage = discount_percent;
              
              // Calculate discount in selected currency
              const discount_amount = vm.flt((item.price_list_rate * discount_percent) / 100, vm.currency_precision);
              item.discount_amount = discount_amount;
              item.rate = vm.flt(item.price_list_rate - discount_amount, vm.currency_precision);
            }
            
            // Update other item details
            item.last_purchase_rate = data.last_purchase_rate;
            item.projected_qty = data.projected_qty;
            item.reserved_qty = data.reserved_qty;
            item.conversion_factor = data.conversion_factor;
            item.stock_qty = data.stock_qty;
            item.actual_qty = data.actual_qty;
            item.stock_uom = data.stock_uom;
            item.has_serial_no = data.has_serial_no;
            item.has_batch_no = data.has_batch_no;
            
            // Calculate final amount
            item.amount = vm.flt(item.qty * item.rate, vm.currency_precision);
            item.base_amount = vm.flt(item.qty * item.base_rate, vm.currency_precision);
            
            // Force update UI immediately
            vm.$forceUpdate();
          }
        },
      });
    },

    // Fetch customer details (info, price list, etc)
    fetch_customer_details() {
      var vm = this;
      if (this.customer) {
        frappe.call({
          method: "posawesome.posawesome.api.posapp.get_customer_info",
          args: {
            customer: vm.customer,
          },
          async: false,
          callback: (r) => {
            const message = r.message;
            if (!r.exc) {
              vm.customer_info = {
                ...message,
              };
            }
            vm.update_price_list();
          },
        });
      }
    },

    // Get price list for current customer
    get_price_list() {
      let price_list = this.pos_profile.selling_price_list;
      if (this.customer_info && this.pos_profile) {
        const { customer_price_list, customer_group_price_list } =
          this.customer_info;
        const pos_price_list = this.pos_profile.selling_price_list;
        if (customer_price_list && customer_price_list != pos_price_list) {
          price_list = customer_price_list;
        } else if (
          customer_group_price_list &&
          customer_group_price_list != pos_price_list
        ) {
          price_list = customer_group_price_list;
        }
      }
      return price_list;
    },

    // Update price list for customer
    update_price_list() {
      let price_list = this.get_price_list();
      if (price_list == this.pos_profile.selling_price_list) {
        price_list = null;
      }
      this.eventBus.emit("update_customer_price_list", price_list);
    },

    // Update additional discount amount based on percentage
    update_discount_umount() {
      const value = flt(this.additional_discount_percentage);
      // If value is too large, reset to 0
      if (value < -100 || value > 100) {
        this.additional_discount_percentage = 0;
        this.additional_discount = 0;
        return;
      }

      // Calculate discount amount based on percentage
      if (this.Total && this.Total !== 0) {
        this.additional_discount = (this.Total * value) / 100;
      } else {
        this.additional_discount = 0;
      }
    },

    // Calculate prices and discounts for an item based on field change
    calc_prices(item, value, $event) {
      if (!$event?.target?.id || !item) return;

      const fieldId = $event.target.id;
      let newValue = flt(value, this.currency_precision);

      try {
        // Handle negative values
        if (newValue < 0) {
          newValue = 0;
          this.eventBus.emit("show_message", {
            title: __("Negative values not allowed"),
            color: "error"
          });
        }

        // Convert price_list_rate to current currency for calculations
        const converted_price_list_rate = this.selected_currency !== this.pos_profile.currency ?
          this.flt(item.price_list_rate / this.exchange_rate, this.currency_precision) :
          item.price_list_rate;

        // Field-wise calculations
        switch (fieldId) {
          case "rate":
            // Store base rate and convert to selected currency
            item.base_rate = this.flt(newValue * this.exchange_rate, this.currency_precision);
            item.rate = newValue;

            // Calculate discount amount in selected currency
            item.discount_amount = this.flt(converted_price_list_rate - item.rate, this.currency_precision);
            item.base_discount_amount = this.flt(item.price_list_rate - item.base_rate, this.currency_precision);

            // Calculate percentage based on converted values
            if (converted_price_list_rate) {
              item.discount_percentage = this.flt((item.discount_amount / converted_price_list_rate) * 100, this.float_precision);
            }
            break;

          case "discount_amount":
            console.log("[calc_prices] Event Target ID:", fieldId);
            console.log("[calc_prices] RAW value received by function:", value); // <-- ADDED THIS
            console.log("[calc_prices] Original item.price_list_rate:", item.price_list_rate);
            console.log("[calc_prices] Converted price_list_rate for calc:", converted_price_list_rate);
            console.log("[calc_prices] Input value (newValue before Math.min):", newValue);

            // Ensure discount amount doesn't exceed price list rate
            newValue = Math.min(newValue, converted_price_list_rate);
            console.log("[calc_prices] Input value (newValue after Math.min):", newValue);

            // Store base discount and convert to selected currency
            item.base_discount_amount = this.flt(newValue * this.exchange_rate, this.currency_precision);
            item.discount_amount = newValue;
            console.log("[calc_prices] Updated item.discount_amount:", item.discount_amount);
            console.log("[calc_prices] Updated item.base_discount_amount:", item.base_discount_amount);

            // Update rate based on discount
            item.rate = this.flt(converted_price_list_rate - item.discount_amount, this.currency_precision);
            item.base_rate = this.flt(item.price_list_rate - item.base_discount_amount, this.currency_precision);
            console.log("[calc_prices] Calculated item.rate:", item.rate);
            console.log("[calc_prices] Calculated item.base_rate:", item.base_rate);

            // Calculate percentage
            if (converted_price_list_rate) {
              item.discount_percentage = this.flt((item.discount_amount / converted_price_list_rate) * 100, this.float_precision);
            } else {
              item.discount_percentage = 0; // Avoid division by zero
            }
            console.log("[calc_prices] Calculated item.discount_percentage:", item.discount_percentage);
            break;

          case "discount_percentage":
            // Ensure percentage doesn't exceed 100%
            newValue = Math.min(newValue, 100);
            item.discount_percentage = this.flt(newValue, this.float_precision);

            // Calculate discount amount in selected currency
            item.discount_amount = this.flt((converted_price_list_rate * item.discount_percentage) / 100, this.currency_precision);
            item.base_discount_amount = this.flt((item.price_list_rate * item.discount_percentage) / 100, this.currency_precision);

            // Update rates
            item.rate = this.flt(converted_price_list_rate - item.discount_amount, this.currency_precision);
            item.base_rate = this.flt(item.price_list_rate - item.base_discount_amount, this.currency_precision);
            break;
        }

        // Ensure rate doesn't go below zero
        if (item.rate < 0) {
          item.rate = 0;
          item.base_rate = 0;
          item.discount_amount = converted_price_list_rate;
          item.base_discount_amount = item.price_list_rate;
          item.discount_percentage = 100;
        }

        // Update stock calculations and force UI update
        this.calc_stock_qty(item, item.qty);
        this.$forceUpdate();

      } catch (error) {
        console.error("Error calculating prices:", error);
        this.eventBus.emit("show_message", {
          title: __("Error calculating prices"),
          color: "error"
        });
      }
    },

    // Calculate item price and discount fields
    calc_item_price(item) {
      if (!item.posa_offer_applied) {
        if (item.price_list_rate) {
          // Always work with base rates first
          if (!item.base_price_list_rate) {
            item.base_price_list_rate = item.price_list_rate;
            item.base_rate = item.rate;
          }

          // Convert to selected currency
          if (this.selected_currency !== this.pos_profile.currency) {
            // If exchange rate is 300 PKR = 1 USD
            // To convert PKR to USD: divide by exchange rate
            // Example: 3000 PKR / 300 = 10 USD
            item.price_list_rate = this.flt(item.base_price_list_rate / this.exchange_rate, this.currency_precision);
            item.rate = this.flt(item.base_rate / this.exchange_rate, this.currency_precision);
          } else {
            item.price_list_rate = item.base_price_list_rate;
            item.rate = item.base_rate;
          }
        }
      }

      // Handle discounts
      if (item.discount_percentage) {
        // Calculate discount in selected currency
        const price_list_rate = item.price_list_rate;
        const discount_amount = this.flt((price_list_rate * item.discount_percentage) / 100, this.currency_precision);
        
        item.discount_amount = discount_amount;
        item.rate = this.flt(price_list_rate - discount_amount, this.currency_precision);
        
        // Store base discount amount
        if (this.selected_currency !== this.pos_profile.currency) {
          // Convert discount amount back to base currency by multiplying with exchange rate
          item.base_discount_amount = this.flt(discount_amount * this.exchange_rate, this.currency_precision);
        } else {
          item.base_discount_amount = item.discount_amount;
        }
      }

      // Calculate amounts
      item.amount = this.flt(item.qty * item.rate, this.currency_precision);
      if (this.selected_currency !== this.pos_profile.currency) {
        // Convert amount back to base currency by multiplying with exchange rate
        item.base_amount = this.flt(item.amount * this.exchange_rate, this.currency_precision);
      } else {
        item.base_amount = item.amount;
      }
      
      this.$forceUpdate();
    },

    // Update UOM (unit of measure) for an item and recalculate prices
    calc_uom(item, value) {
      const new_uom = item.item_uoms.find((element) => element.uom == value);
      if (!new_uom) {
        this.eventBus.emit("show_message", {
          title: __("UOM not found"),
          color: "error",
        });
        return;
      }

      // Store old conversion factor for ratio calculation
      const old_conversion_factor = item.conversion_factor || 1;
      
      // Update conversion factor
      item.conversion_factor = new_uom.conversion_factor;

      // Calculate the ratio of new to old conversion factor
      const conversion_ratio = item.conversion_factor / old_conversion_factor;

      // Reset discount if not offer
      if (!item.posa_offer_applied) {
        item.discount_amount = 0;
        item.discount_percentage = 0;
      }
      
      // Store original base rates if not already stored
      if (!item.original_base_rate && !item.posa_offer_applied) {
        item.original_base_rate = item.base_rate / old_conversion_factor;
        item.original_base_price_list_rate = item.base_price_list_rate / old_conversion_factor;
      }

      // Update rates based on new conversion factor
      if (item.posa_offer_applied) {
        // For items with offer, recalculate from original offer rate
        const offer = this.posOffers.find(o => {
          const items = typeof o.items === 'string' ? JSON.parse(o.items) : o.items;
          return items.includes(item.posa_row_id) && o.discount_type === 'Rate';
        });
        
        if (offer) {
          // Apply offer rate with new conversion factor
          const converted_rate = flt(offer.rate * item.conversion_factor);
          
          // Set base rates
          item.base_rate = converted_rate;
          item.base_price_list_rate = converted_rate;
          
          // Convert to selected currency
          if (this.selected_currency !== this.pos_profile.currency) {
            // If exchange rate is 300 PKR = 1 USD
            // To convert PKR to USD: divide by exchange rate
            // Example: 3000 PKR / 300 = 10 USD
            item.rate = this.flt(converted_rate / this.exchange_rate, this.currency_precision);
            item.price_list_rate = item.rate;
          } else {
            item.rate = converted_rate;
            item.price_list_rate = converted_rate;
          }
        }
      } else {
        // For regular items, use standard conversion
        if (item.batch_price) {
          item.base_rate = item.batch_price * item.conversion_factor;
          item.base_price_list_rate = item.base_rate;
        } else if (item.original_base_rate) {
          item.base_rate = item.original_base_rate * item.conversion_factor;
          item.base_price_list_rate = item.original_base_price_list_rate * item.conversion_factor;
        }
        
        // Convert to selected currency
        if (this.selected_currency !== this.pos_profile.currency) {
          // If exchange rate is 300 PKR = 1 USD
          // To convert PKR to USD: divide by exchange rate
          // Example: 3000 PKR / 300 = 10 USD
          item.rate = this.flt(item.base_rate / this.exchange_rate, this.currency_precision);
          item.price_list_rate = this.flt(item.base_price_list_rate / this.exchange_rate, this.currency_precision);
        } else {
          item.rate = item.base_rate;
          item.price_list_rate = item.base_price_list_rate;
        }
      }

      // Update item details
      this.calc_stock_qty(item, item.qty);
      this.$forceUpdate();
    },

    // Calculate stock quantity for an item
    calc_stock_qty(item, value) {
      item.stock_qty = item.conversion_factor * value;
    },

    // Set serial numbers for an item (and update qty)
    set_serial_no(item) {
      console.log(item)
      if (!item.has_serial_no) return;
      item.serial_no = "";
      item.serial_no_selected.forEach((element) => {
        item.serial_no += element + "\n";
      });
      item.serial_no_selected_count = item.serial_no_selected.length;
      if (item.serial_no_selected_count != item.stock_qty) {
        item.qty = item.serial_no_selected_count;
        this.calc_stock_qty(item, item.qty);
        this.$forceUpdate();
      }
    },

    // Set batch number for an item (and update batch data)
    set_batch_qty(item, value, update = true) {
      console.log('Setting batch quantity:', item, value);
      const existing_items = this.items.filter(
        (element) =>
          element.item_code == item.item_code &&
          element.posa_row_id != item.posa_row_id
      );
      const used_batches = {};
      item.batch_no_data.forEach((batch) => {
        used_batches[batch.batch_no] = {
          ...batch,
          used_qty: 0,
          remaining_qty: batch.batch_qty,
        };
        existing_items.forEach((element) => {
          if (element.batch_no && element.batch_no == batch.batch_no) {
            used_batches[batch.batch_no].used_qty += element.qty;
            used_batches[batch.batch_no].remaining_qty -= element.qty;
            used_batches[batch.batch_no].batch_qty -= element.qty;
          }
        });
      });

      const batch_no_data = Object.values(used_batches)
        .filter((batch) => batch.remaining_qty > 0)
        .sort((a, b) => {
          if (a.expiry_date && b.expiry_date) {
            return new Date(a.expiry_date) - new Date(b.expiry_date);
          } else if (a.expiry_date) {
            return -1;
          } else if (b.expiry_date) {
            return 1;
          } else if (a.manufacturing_date && b.manufacturing_date) {
            return new Date(a.manufacturing_date) - new Date(b.manufacturing_date);
          } else if (a.manufacturing_date) {
            return -1;
          } else if (b.manufacturing_date) {
            return 1;
          } else {
            return b.remaining_qty - a.remaining_qty;
          }
        });
      
      if (batch_no_data.length > 0) {
        let batch_to_use = null;
        if (value) {
          batch_to_use = batch_no_data.find((batch) => batch.batch_no == value);
        }
        if (!batch_to_use) {
          batch_to_use = batch_no_data[0];
        }
        
        item.batch_no = batch_to_use.batch_no;
        item.actual_batch_qty = batch_to_use.batch_qty;
        item.batch_no_expiry_date = batch_to_use.expiry_date;
        
        if (batch_to_use.batch_price) {
          // Store batch price in base currency
          item.base_batch_price = batch_to_use.batch_price;
          
          // Convert batch price to selected currency if needed
          if (this.selected_currency !== this.pos_profile.currency) {
            // If exchange rate is 285 PKR = 1 USD
            // To convert PKR to USD: divide by exchange rate
            item.batch_price = this.flt(batch_to_use.batch_price / this.exchange_rate, this.currency_precision);
          } else {
            item.batch_price = batch_to_use.batch_price;
          }
          
          // Set rates based on batch price
          item.base_price_list_rate = item.base_batch_price;
          item.base_rate = item.base_batch_price;
          
          if (this.selected_currency !== this.pos_profile.currency) {
            item.price_list_rate = item.batch_price;
            item.rate = item.batch_price;
          } else {
            item.price_list_rate = item.base_batch_price;
            item.rate = item.base_batch_price;
          }
          
          // Reset discounts since we're using batch price
          item.discount_percentage = 0;
          item.discount_amount = 0;
          item.base_discount_amount = 0;
          
          // Calculate final amounts
          item.amount = this.flt(item.qty * item.rate, this.currency_precision);
          item.base_amount = this.flt(item.qty * item.base_rate, this.currency_precision);
          
          console.log('Updated batch prices:', {
            base_batch_price: item.base_batch_price,
            batch_price: item.batch_price,
            rate: item.rate,
            base_rate: item.base_rate,
            price_list_rate: item.price_list_rate,
            exchange_rate: this.exchange_rate
          });
          
        } else if (update) {
          item.batch_price = null;
          item.base_batch_price = null;
          this.update_item_detail(item);
        }
      } else {
        item.batch_no = null;
        item.actual_batch_qty = null;
        item.batch_no_expiry_date = null;
        item.batch_price = null;
        item.base_batch_price = null;
      }
      
      // Update batch_no_data
      item.batch_no_data = batch_no_data;
      
      // Force UI update
      this.$forceUpdate();
    },

    // Keyboard shortcut: open payment dialog
    shortOpenPayment(e) {
      if (e.key === "s" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.show_payment();
      }
    },

    // Keyboard shortcut: delete first item from the invoice
    shortDeleteFirstItem(e) {
      if (e.key === "d" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.remove_item(this.items[0]);
      }
    },

    shortSelectDiscount(e) {
      console.log('Shortcut pressed:', e.key, e.ctrlKey);
      if (e.key.toLowerCase() === "e" && (e.ctrlKey || e.metaKey)) {
        console.log('Focusing discount field');
        e.preventDefault();
        e.stopPropagation();
        if (this.$refs.discount) {
          this.$refs.discount.focus();
          console.log('Discount field focused');
        } else {
          console.log('Discount field ref not found');
        }
      }
    },

    makeid(length) {
      let result = "";
      const characters = "abcdefghijklmnopqrstuvwxyz0123456789";
      const charactersLength = characters.length;
      for (var i = 0; i < length; i++) {
        result += characters.charAt(
          Math.floor(Math.random() * charactersLength)
        );
      }
      return result;
    },

    checkOfferIsAppley(item, offer) {
      let applied = false;
      const item_offers = JSON.parse(item.posa_offers);
      for (const row_id of item_offers) {
        const exist_offer = this.posa_offers.find((el) => row_id == el.row_id);
        if (exist_offer && exist_offer.offer_name == offer.name) {
          applied = true;
          break;
        }
      }
      return applied;
    },

    handelOffers() {
      const offers = [];
      this.posOffers.forEach((offer) => {
        if (offer.apply_on === "Item Code") {
          const itemOffer = this.getItemOffer(offer);
          if (itemOffer) {
            offers.push(itemOffer);
          }
        } else if (offer.apply_on === "Item Group") {
          const groupOffer = this.getGroupOffer(offer);
          if (groupOffer) {
            offers.push(groupOffer);
          }
        } else if (offer.apply_on === "Brand") {
          const brandOffer = this.getBrandOffer(offer);
          if (brandOffer) {
            offers.push(brandOffer);
          }
        } else if (offer.apply_on === "Transaction") {
          const transactionOffer = this.getTransactionOffer(offer);
          if (transactionOffer) {
            offers.push(transactionOffer);
          }
        }
      });

      this.setItemGiveOffer(offers);
      this.updatePosOffers(offers);
    },

    setItemGiveOffer(offers) {
      // Set item give offer for replace
      offers.forEach((offer) => {
        if (
          offer.apply_on == "Item Code" &&
          offer.apply_type == "Item Code" &&
          offer.replace_item
        ) {
          offer.give_item = offer.item;
          offer.apply_item_code = offer.item;
        } else if (
          offer.apply_on == "Item Group" &&
          offer.apply_type == "Item Group" &&
          offer.replace_cheapest_item
        ) {
          const offerItemCode = this.getCheapestItem(offer).item_code;
          offer.give_item = offerItemCode;
          offer.apply_item_code = offerItemCode;
        }
      });
    },

    getCheapestItem(offer) {
      let itemsRowID;
      if (typeof offer.items === "string") {
        itemsRowID = JSON.parse(offer.items);
      } else {
        itemsRowID = offer.items;
      }
      const itemsList = [];
      itemsRowID.forEach((row_id) => {
        itemsList.push(this.getItemFromRowID(row_id));
      });
      const result = itemsList.reduce(function (res, obj) {
        return !obj.posa_is_replace &&
          !obj.posa_is_offer &&
          obj.price_list_rate < res.price_list_rate
          ? obj
          : res;
      });
      return result;
    },

    getItemFromRowID(row_id) {
      const item = this.items.find((el) => el.posa_row_id == row_id);
      return item;
    },

    checkQtyAnountOffer(offer, qty, amount) {
      let min_qty = false;
      let max_qty = false;
      let min_amt = false;
      let max_amt = false;
      const applys = [];

      if (offer.min_qty || offer.min_qty == 0) {
        if (qty >= offer.min_qty) {
          min_qty = true;
        }
        applys.push(min_qty);
      }

      if (offer.max_qty > 0) {
        if (qty <= offer.max_qty) {
          max_qty = true;
        }
        applys.push(max_qty);
      }

      if (offer.min_amt > 0) {
        if (amount >= offer.min_amt) {
          min_amt = true;
        }
        applys.push(min_amt);
      }

      if (offer.max_amt > 0) {
        if (amount <= offer.max_amt) {
          max_amt = true;
        }
        applys.push(max_amt);
      }
      let apply = false;
      if (!applys.includes(false)) {
        apply = true;
      }
      const res = {
        apply: apply,
        conditions: { min_qty, max_qty, min_amt, max_amt },
      };
      return res;
    },

    checkOfferCoupon(offer) {
      if (offer.coupon_based) {
        const coupon = this.posa_coupons.find(
          (el) => offer.name == el.pos_offer
        );
        if (coupon) {
          offer.coupon = coupon.coupon;
          return true;
        } else {
          return false;
        }
      } else {
        offer.coupon = null;
        return true;
      }
    },

    getItemOffer(offer) {
      let apply_offer = null;
      if (offer.apply_on === "Item Code") {
        if (this.checkOfferCoupon(offer)) {
          this.items.forEach((item) => {
            if (!item.posa_is_offer && item.item_code === offer.item) {
              const items = [];
              if (
                offer.offer === "Item Price" &&
                item.posa_offer_applied &&
                !this.checkOfferIsAppley(item, offer)
              ) {
              } else {
                const res = this.checkQtyAnountOffer(
                  offer,
                  item.stock_qty,
                  item.stock_qty * item.price_list_rate
                );
                if (res.apply) {
                  items.push(item.posa_row_id);
                  offer.items = items;
                  apply_offer = offer;
                }
              }
            }
          });
        }
      }
      return apply_offer;
    },

    getGroupOffer(offer) {
      let apply_offer = null;
      if (offer.apply_on === "Item Group") {
        if (this.checkOfferCoupon(offer)) {
          const items = [];
          let total_count = 0;
          let total_amount = 0;
          this.items.forEach((item) => {
            if (!item.posa_is_offer && item.item_group === offer.item_group) {
              if (
                offer.offer === "Item Price" &&
                item.posa_offer_applied &&
                !this.checkOfferIsAppley(item, offer)
              ) {
              } else {
                total_count += item.stock_qty;
                total_amount += item.stock_qty * item.price_list_rate;
                items.push(item.posa_row_id);
              }
            }
          });
          if (total_count || total_amount) {
            const res = this.checkQtyAnountOffer(
              offer,
              total_count,
              total_amount
            );
            if (res.apply) {
              offer.items = items;
              apply_offer = offer;
            }
          }
        }
      }
      return apply_offer;
    },

    getBrandOffer(offer) {
      let apply_offer = null;
      if (offer.apply_on === "Brand") {
        if (this.checkOfferCoupon(offer)) {
          const items = [];
          let total_count = 0;
          let total_amount = 0;
          this.items.forEach((item) => {
            if (!item.posa_is_offer && item.brand === offer.brand) {
              if (
                offer.offer === "Item Price" &&
                item.posa_offer_applied &&
                !this.checkOfferIsAppley(item, offer)
              ) {
              } else {
                total_count += item.stock_qty;
                total_amount += item.stock_qty * item.price_list_rate;
                items.push(item.posa_row_id);
              }
            }
          });
          if (total_count || total_amount) {
            const res = this.checkQtyAnountOffer(
              offer,
              total_count,
              total_amount
            );
            if (res.apply) {
              offer.items = items;
              apply_offer = offer;
            }
          }
        }
      }
      return apply_offer;
    },
    getTransactionOffer(offer) {
      let apply_offer = null;
      if (offer.apply_on === "Transaction") {
        if (this.checkOfferCoupon(offer)) {
          let total_qty = 0;
          this.items.forEach((item) => {
            if (!item.posa_is_offer && !item.posa_is_replace) {
              total_qty += item.stock_qty;
            }
          });
          const items = [];
          const total_count = total_qty;
          const total_amount = this.Total;
          if (total_count || total_amount) {
            const res = this.checkQtyAnountOffer(
              offer,
              total_count,
              total_amount
            );
            if (res.apply) {
              this.items.forEach((item) => {
                items.push(item.posa_row_id);
              });
              offer.items = items;
              apply_offer = offer;
            }
          }
        }
      }
      return apply_offer;
    },

    updatePosOffers(offers) {
      this.eventBus.emit("update_pos_offers", offers);
    },

    updateInvoiceOffers(offers) {
      this.posa_offers.forEach((invoiceOffer) => {
        const existOffer = offers.find(
          (offer) => invoiceOffer.row_id == offer.row_id
        );
        if (!existOffer) {
          this.removeApplyOffer(invoiceOffer);
        }
      });
      offers.forEach((offer) => {
        const existOffer = this.posa_offers.find(
          (invoiceOffer) => invoiceOffer.row_id == offer.row_id
        );
        if (existOffer) {
          existOffer.items = JSON.stringify(offer.items);
          if (
            existOffer.offer === "Give Product" &&
            existOffer.give_item &&
            existOffer.give_item != offer.give_item
          ) {
            const item_to_remove = this.items.find(
              (item) => item.posa_row_id == existOffer.give_item_row_id
            );
            if (item_to_remove) {
              const updated_item_offers = offer.items.filter(
                (row_id) => row_id != item_to_remove.posa_row_id
              );
              offer.items = updated_item_offers;
              this.remove_item(item_to_remove);
              existOffer.give_item_row_id = null;
              existOffer.give_item = null;
            }
            const newItemOffer = this.ApplyOnGiveProduct(offer);
            if (offer.replace_cheapest_item) {
              const cheapestItem = this.getCheapestItem(offer);
              const oldBaseItem = this.items.find(
                (el) => el.posa_row_id == item_to_remove.posa_is_replace
              );
              newItemOffer.qty = item_to_remove.qty;
              if (oldBaseItem && !oldBaseItem.posa_is_replace) {
                oldBaseItem.qty += item_to_remove.qty;
              } else {
                const restoredItem = this.ApplyOnGiveProduct(
                  {
                    given_qty: item_to_remove.qty,
                  },
                  item_to_remove.item_code
                );
                restoredItem.posa_is_offer = 0;
                this.items.unshift(restoredItem);
              }
              newItemOffer.posa_is_offer = 0;
              newItemOffer.posa_is_replace = cheapestItem.posa_row_id;
              const diffQty = cheapestItem.qty - newItemOffer.qty;
              if (diffQty <= 0) {
                newItemOffer.qty += diffQty;
                this.remove_item(cheapestItem);
                newItemOffer.posa_row_id = cheapestItem.posa_row_id;
                newItemOffer.posa_is_replace = newItemOffer.posa_row_id;
              } else {
                cheapestItem.qty = diffQty;
              }
            }
            this.items.unshift(newItemOffer);
            existOffer.give_item_row_id = newItemOffer.posa_row_id;
            existOffer.give_item = newItemOffer.item_code;
          } else if (
            existOffer.offer === "Give Product" &&
            existOffer.give_item &&
            existOffer.give_item == offer.give_item &&
            (offer.replace_item || offer.replace_cheapest_item)
          ) {
            this.$nextTick(function () {
              const offerItem = this.getItemFromRowID(
                existOffer.give_item_row_id
              );
              const diff = offer.given_qty - offerItem.qty;
              if (diff > 0) {
                const itemsRowID = JSON.parse(existOffer.items);
                const itemsList = [];
                itemsRowID.forEach((row_id) => {
                  itemsList.push(this.getItemFromRowID(row_id));
                });
                const existItem = itemsList.find(
                  (el) =>
                    el.item_code == offerItem.item_code &&
                    el.posa_is_replace != offerItem.posa_row_id
                );
                if (existItem) {
                  const diffExistQty = existItem.qty - diff;
                  if (diffExistQty > 0) {
                    offerItem.qty += diff;
                    existItem.qty -= diff;
                  } else {
                    offerItem.qty += existItem.qty;
                    this.remove_item(existItem);
                  }
                }
              }
            });
          } else if (existOffer.offer === "Item Price") {
            this.ApplyOnPrice(offer);
          } else if (existOffer.offer === "Grand Total") {
            this.ApplyOnTotal(offer);
          }
          this.addOfferToItems(existOffer);
        } else {
          this.applyNewOffer(offer);
        }
      });
    },

    removeApplyOffer(invoiceOffer) {
      if (invoiceOffer.offer === "Item Price") {
        this.RemoveOnPrice(invoiceOffer);
        const index = this.posa_offers.findIndex(
          (el) => el.row_id === invoiceOffer.row_id
        );
        this.posa_offers.splice(index, 1);
      }
      if (invoiceOffer.offer === "Give Product") {
        const item_to_remove = this.items.find(
          (item) => item.posa_row_id == invoiceOffer.give_item_row_id
        );
        const index = this.posa_offers.findIndex(
          (el) => el.row_id === invoiceOffer.row_id
        );
        this.posa_offers.splice(index, 1);
        this.remove_item(item_to_remove);
      }
      if (invoiceOffer.offer === "Grand Total") {
        this.RemoveOnTotal(invoiceOffer);
        const index = this.posa_offers.findIndex(
          (el) => el.row_id === invoiceOffer.row_id
        );
        this.posa_offers.splice(index, 1);
      }
      if (invoiceOffer.offer === "Loyalty Point") {
        const index = this.posa_offers.findIndex(
          (el) => el.row_id === invoiceOffer.row_id
        );
        this.posa_offers.splice(index, 1);
      }
      this.deleteOfferFromItems(invoiceOffer);
    },

    applyNewOffer(offer) {
      if (offer.offer === "Item Price") {
        this.ApplyOnPrice(offer);
      }
      if (offer.offer === "Give Product") {
        let itemsRowID;
        if (typeof offer.items === "string") {
          itemsRowID = JSON.parse(offer.items);
        } else {
          itemsRowID = offer.items;
        }
        if (
          offer.apply_on == "Item Code" &&
          offer.apply_type == "Item Code" &&
          offer.replace_item
        ) {
          const item = this.ApplyOnGiveProduct(offer, offer.item);
          item.posa_is_replace = itemsRowID[0];
          const baseItem = this.items.find(
            (el) => el.posa_row_id == item.posa_is_replace
          );
          const diffQty = baseItem.qty - offer.given_qty;
          item.posa_is_offer = 0;
          if (diffQty <= 0) {
            item.qty = baseItem.qty;
            this.remove_item(baseItem);
            item.posa_row_id = item.posa_is_replace;
          } else {
            baseItem.qty = diffQty;
          }
          this.items.unshift(item);
          offer.give_item_row_id = item.posa_row_id;
        } else if (
          offer.apply_on == "Item Group" &&
          offer.apply_type == "Item Group" &&
          offer.replace_cheapest_item
        ) {
          const itemsList = [];
          itemsRowID.forEach((row_id) => {
            itemsList.push(this.getItemFromRowID(row_id));
          });
          const baseItem = itemsList.find(
            (el) => el.item_code == offer.give_item
          );
          const item = this.ApplyOnGiveProduct(offer, offer.give_item);
          item.posa_is_offer = 0;
          item.posa_is_replace = baseItem.posa_row_id;
          const diffQty = baseItem.qty - offer.given_qty;
          if (diffQty <= 0) {
            item.qty = baseItem.qty;
            this.remove_item(baseItem);
            item.posa_row_id = item.posa_is_replace;
          } else {
            baseItem.qty = diffQty;
          }
          this.items.unshift(item);
          offer.give_item_row_id = item.posa_row_id;
        } else {
          const item = this.ApplyOnGiveProduct(offer);
          this.items.unshift(item);
          if (item) {
            offer.give_item_row_id = item.posa_row_id;
          }
        }
      }
      if (offer.offer === "Grand Total") {
        this.ApplyOnTotal(offer);
      }
      if (offer.offer === "Loyalty Point") {
        this.eventBus.emit("show_message", {
          title: __("Loyalty Point Offer Applied"),
          color: "success",
        });
      }

      const newOffer = {
        offer_name: offer.name,
        row_id: offer.row_id,
        apply_on: offer.apply_on,
        offer: offer.offer,
        items: JSON.stringify(offer.items),
        give_item: offer.give_item,
        give_item_row_id: offer.give_item_row_id,
        offer_applied: offer.offer_applied,
        coupon_based: offer.coupon_based,
        coupon: offer.coupon,
      };
      this.posa_offers.push(newOffer);
      this.addOfferToItems(newOffer);
    },

    ApplyOnGiveProduct(offer, item_code) {
      if (!item_code) {
        item_code = offer.give_item;
      }
      const items = this.allItems;
      const item = items.find((item) => item.item_code == item_code);
      if (!item) {
        return;
      }
      const new_item = { ...item };
      new_item.qty = offer.given_qty;
      new_item.stock_qty = offer.given_qty;

      // Handle rate based on currency
      if (offer.discount_type === "Rate") {
        // offer.rate is always in base currency (PKR)
        new_item.base_rate = offer.rate;
        if (this.selected_currency !== this.pos_profile.currency) {
          // If exchange rate is 300 PKR = 1 USD
          // Convert PKR to USD by dividing
          new_item.rate = this.flt(offer.rate / this.exchange_rate, this.currency_precision);
        } else {
          new_item.rate = offer.rate;
        }
      } else {
        // Use item's original rate
        if (this.selected_currency !== this.pos_profile.currency) {
          new_item.base_rate = item.base_rate || (item.rate * this.exchange_rate);
          new_item.rate = item.rate;
        } else {
          new_item.base_rate = item.rate;
          new_item.rate = item.rate;
        }
      }

      // Handle discount amount based on currency
      if (offer.discount_type === "Discount Amount") {
        // offer.discount_amount is always in base currency (PKR)
        new_item.base_discount_amount = offer.discount_amount;
        if (this.selected_currency !== this.pos_profile.currency) {
          // Convert PKR to USD by dividing
          new_item.discount_amount = this.flt(offer.discount_amount / this.exchange_rate, this.currency_precision);
        } else {
          new_item.discount_amount = offer.discount_amount;
        }
      } else {
        new_item.base_discount_amount = 0;
        new_item.discount_amount = 0;
      }

      new_item.discount_percentage = offer.discount_type === "Discount Percentage" ? offer.discount_percentage : 0;
      new_item.discount_amount_per_item = 0;
      new_item.uom = item.uom ? item.uom : item.stock_uom;
      new_item.actual_batch_qty = "";
      new_item.conversion_factor = 1;
      new_item.posa_offers = JSON.stringify([]);
      new_item.posa_offer_applied = 0;
      new_item.posa_is_offer = 1;
      new_item.posa_is_replace = null;
      new_item.posa_notes = "";
      new_item.posa_delivery_date = "";

      // Handle free items
      const is_free = (offer.discount_type === "Rate" && !offer.rate) ||
        (offer.discount_type === "Discount Percentage" && offer.discount_percentage == 100);
      
      new_item.is_free_item = is_free ? 1 : 0;

      // Set price list rate based on currency
      if (is_free) {
        new_item.base_price_list_rate = 0;
        new_item.price_list_rate = 0;
      } else {
        // item.rate is in base currency (PKR)
        new_item.base_price_list_rate = item.rate;
        if (this.selected_currency !== this.pos_profile.currency) {
          // Convert PKR to USD by dividing
          new_item.price_list_rate = this.flt(item.rate / this.exchange_rate, this.currency_precision);
        } else {
          new_item.price_list_rate = item.rate;
        }
      }

      new_item.posa_row_id = this.makeid(20);

      if ((!this.pos_profile.posa_auto_set_batch && new_item.has_batch_no) || new_item.has_serial_no) {
        this.expanded.push(new_item);
      }

      this.update_item_detail(new_item);
      return new_item;
    },

    ApplyOnPrice(offer) {
      console.log('Applying price offer:', offer);
      this.items.forEach((item) => {
        if (offer.items.includes(item.posa_row_id)) {
          const item_offers = JSON.parse(item.posa_offers);
          if (!item_offers.includes(offer.row_id)) {
            // Store original rates only if this is the first offer being applied
            if (!item.posa_offer_applied) {
              item.original_base_rate = item.base_rate;
              item.original_base_price_list_rate = item.base_price_list_rate;
              item.original_rate = item.rate;
              item.original_price_list_rate = item.price_list_rate;
              console.log('Storing original rates:', {
                original_base_rate: item.original_base_rate,
                original_base_price_list_rate: item.original_base_price_list_rate,
                original_rate: item.original_rate,
                original_price_list_rate: item.original_price_list_rate
              });
            }

            const conversion_factor = flt(item.conversion_factor || 1);

            if (offer.discount_type === "Rate") {
              // offer.rate is always in base currency (e.g. PKR)
              const base_offer_rate = flt(offer.rate * conversion_factor);
              
              // Set base rates first
              item.base_rate = base_offer_rate;
              item.base_price_list_rate = base_offer_rate;

              // Convert to selected currency if needed
              if (this.selected_currency !== this.pos_profile.currency) {
                // If exchange rate is 285 PKR = 1 USD
                // To convert PKR to USD: divide by exchange rate
                item.rate = this.flt(base_offer_rate / this.exchange_rate, this.currency_precision);
                item.price_list_rate = item.rate;
              } else {
                item.rate = base_offer_rate;
                item.price_list_rate = base_offer_rate;
              }

              // Reset discounts since we're setting rate directly
              item.discount_percentage = 0;
              item.discount_amount = 0;
              item.base_discount_amount = 0;

            } else if (offer.discount_type === "Discount Percentage") {
              item.discount_percentage = offer.discount_percentage;
              
              // Calculate discount in base currency first
              const base_price = item.original_base_price_list_rate || item.base_price_list_rate;
              const base_discount = this.flt((base_price * offer.discount_percentage) / 100, this.currency_precision);
              item.base_discount_amount = base_discount;
              item.base_rate = this.flt(base_price - base_discount, this.currency_precision);

              // Convert to selected currency if needed
              if (this.selected_currency !== this.pos_profile.currency) {
                const original_price = item.original_price_list_rate || item.price_list_rate;
                item.price_list_rate = this.flt(base_price / this.exchange_rate, this.currency_precision);
                item.discount_amount = this.flt(base_discount / this.exchange_rate, this.currency_precision);
                item.rate = this.flt(item.base_rate / this.exchange_rate, this.currency_precision);
              } else {
                item.price_list_rate = base_price;
                item.discount_amount = base_discount;
                item.rate = item.base_rate;
              }
            }

            // Calculate final amounts
            item.amount = this.flt(item.qty * item.rate, this.currency_precision);
            item.base_amount = this.flt(item.qty * item.base_rate, this.currency_precision);
            
            console.log('Updated rates after applying offer:', {
              rate: item.rate,
              base_rate: item.base_rate,
              price_list_rate: item.price_list_rate,
              base_price_list_rate: item.base_price_list_rate,
              discount_amount: item.discount_amount,
              base_discount_amount: item.base_discount_amount,
              amount: item.amount,
              base_amount: item.base_amount
            });

            item.posa_offer_applied = 1;
            this.$forceUpdate();
          }
        }
      });
    },

    RemoveOnPrice(offer) {
      console.log('Removing price offer:', offer);
      this.items.forEach((item) => {
        const item_offers = JSON.parse(item.posa_offers);
        if (item_offers.includes(offer.row_id)) {
          console.log('Found item with offer:', item);
          
          // Check if we have original rates stored
          if (!item.original_base_rate) {
            console.warn('Original rates not found, fetching from server');
            this.update_item_detail(item);
            return;
          }

          console.log('Restoring original rates:', {
            original_base_rate: item.original_base_rate,
            original_base_price_list_rate: item.original_base_price_list_rate,
            original_rate: item.original_rate,
            original_price_list_rate: item.original_price_list_rate
          });

          // Restore original rates exactly as they were
          item.base_rate = item.original_base_rate;
          item.base_price_list_rate = item.original_base_price_list_rate;
          item.rate = item.original_rate;
          item.price_list_rate = item.original_price_list_rate;

          // Reset all discounts
          item.discount_percentage = 0;
          item.discount_amount = 0;
          item.base_discount_amount = 0;

          // Recalculate amounts
          item.amount = this.flt(item.qty * item.rate, this.currency_precision);
          item.base_amount = this.flt(item.qty * item.base_rate, this.currency_precision);

          // Only clear original rates if no other offers are applied
          const remaining_offers = item_offers.filter(id => id !== offer.row_id);
          if (remaining_offers.length === 0) {
            item.original_base_rate = null;
            item.original_base_price_list_rate = null;
            item.original_rate = null;
            item.original_price_list_rate = null;
            item.posa_offer_applied = 0;
          }

          console.log('Updated rates after removing offer:', {
            rate: item.rate,
            base_rate: item.base_rate,
            price_list_rate: item.price_list_rate,
            base_price_list_rate: item.base_price_list_rate,
            amount: item.amount,
            base_amount: item.base_amount,
            remaining_offers: remaining_offers
          });

          // Force UI update
          this.$forceUpdate();
        }
      });
    },

    ApplyOnTotal(offer) {
      if (!offer.name) {
        offer = this.posOffers.find((el) => el.name == offer.offer_name);
      }
      if (
        (!this.discount_percentage_offer_name ||
          this.discount_percentage_offer_name == offer.name) &&
        offer.discount_percentage > 0 &&
        offer.discount_percentage <= 100
      ) {
        this.discount_amount = this.flt(
          (flt(this.Total) * flt(offer.discount_percentage)) / 100,
          this.currency_precision
        );
        this.discount_percentage_offer_name = offer.name;
      }
    },

    RemoveOnTotal(offer) {
      if (
        this.discount_percentage_offer_name &&
        this.discount_percentage_offer_name == offer.offer_name
      ) {
        this.discount_amount = 0;
        this.discount_percentage_offer_name = null;
      }
    },

    addOfferToItems(offer) {
      const offer_items = JSON.parse(offer.items);
      offer_items.forEach((el) => {
        this.items.forEach((exist_item) => {
          if (exist_item.posa_row_id == el) {
            const item_offers = JSON.parse(exist_item.posa_offers);
            if (!item_offers.includes(offer.row_id)) {
              item_offers.push(offer.row_id);
              if (offer.offer === "Item Price") {
                exist_item.posa_offer_applied = 1;
              }
            }
            exist_item.posa_offers = JSON.stringify(item_offers);
          }
        });
      });
    },

    deleteOfferFromItems(offer) {
      const offer_items = JSON.parse(offer.items);
      offer_items.forEach((el) => {
        this.items.forEach((exist_item) => {
          if (exist_item.posa_row_id == el) {
            const item_offers = JSON.parse(exist_item.posa_offers);
            const updated_item_offers = item_offers.filter(
              (row_id) => row_id != offer.row_id
            );
            if (offer.offer === "Item Price") {
              exist_item.posa_offer_applied = 0;
            }
            exist_item.posa_offers = JSON.stringify(updated_item_offers);
          }
        });
      });
    },

    validate_due_date(item) {
      const today = frappe.datetime.now_date();
      const parse_today = Date.parse(today);
      const new_date = Date.parse(item.posa_delivery_date);
      if (new_date < parse_today) {
        setTimeout(() => {
          item.posa_delivery_date = today;
        }, 0);
      }
    },
    load_print_page(invoice_name) {
      const print_format =
        this.pos_profile.print_format_for_online ||
        this.pos_profile.print_format;
      const letter_head = this.pos_profile.letter_head || 0;
      const url =
        frappe.urllib.get_base_url() +
        "/printview?doctype=Sales%20Invoice&name=" +
        invoice_name +
        "&trigger_print=1" +
        "&format=" +
        print_format +
        "&no_letterhead=" +
        letter_head;
      const printWindow = window.open(url, "Print");
      printWindow.addEventListener(
        "load",
        function () {
          printWindow.print();
          // printWindow.close();
          // NOTE : uncomoent this to auto closing printing window
        },
        true
      );
    },

    toggleOffer(item) {
      this.$nextTick(() => {
        if (!item.posa_is_offer) {
          item.posa_offers = JSON.stringify([]);
          item.posa_offer_applied = 0;
          item.discount_percentage = 0;
          item.discount_amount = 0;
          item.rate = item.price_list_rate;
          this.calc_item_price(item);
          this.handelOffers();
        }
        // Ensure Vue reactivity
        this.$forceUpdate();
      });
    },  // Added missing comma here

    print_draft_invoice() {
      if (!this.pos_profile.posa_allow_print_draft_invoices) {
        this.eventBus.emit("show_message", {
          title: __(`You are not allowed to print draft invoices`),
          color: "error",
        });
        return;
      }
      let invoice_name = this.invoice_doc.name;
      frappe.run_serially([
        () => {
          const invoice_doc = this.save_and_clear_invoice();
          invoice_name = invoice_doc.name ? invoice_doc.name : invoice_name;
        },
        () => {
          this.load_print_page(invoice_name);
        },
      ]);
    },
    set_delivery_charges() {
      var vm = this;
      if (
        !this.pos_profile ||
        !this.customer ||
        !this.pos_profile.posa_use_delivery_charges
      ) {
        this.delivery_charges = [];
        this.delivery_charges_rate = 0;
        this.selected_delivery_charge = "";
        return;
      }
      this.delivery_charges_rate = 0;
      this.selected_delivery_charge = "";
      frappe.call({
        method:
          "posawesome.posawesome.api.posapp.get_applicable_delivery_charges",
        args: {
          company: this.pos_profile.company,
          pos_profile: this.pos_profile.name,
          customer: this.customer,
        },
        async: false,
        callback: function (r) {
          if (r.message) {
            if (r.message?.length) {
              console.log(r.message)
              vm.delivery_charges = r.message;
            }
          }
        },
      });
    },
    deliveryChargesFilter(itemText, queryText, itemRow) {
      const item = itemRow.raw;
      console.log("dl charges", item)
      const textOne = item.name.toLowerCase();
      const searchText = queryText.toLowerCase();
      return textOne.indexOf(searchText) > -1;
    },
    update_delivery_charges() {

      if (this.selected_delivery_charge) {
        this.delivery_charges_rate = this.selected_delivery_charge.rate;
      } else {
        this.delivery_charges_rate = 0;
      }
    },
    updatePostingDate(date) {
      if (!date) return;
      this.posting_date = date;
      this.$forceUpdate();
    },
    // Override setFormatedFloat for qty field to handle return mode
    setFormatedQty(item, field_name, precision, no_negative, value) {
      // Use the regular formatter method from the mixin
      let parsedValue = this.setFormatedFloat(item, field_name, precision, no_negative, value);

      // Ensure negative value for return invoices
      if (this.invoiceType === "Return" && parsedValue > 0) {
        parsedValue = -Math.abs(parsedValue);
        item[field_name] = parsedValue;
      }

      return parsedValue;
    },
    async fetch_available_currencies() {
      try {
        console.log("Fetching available currencies...");
        const r = await frappe.call({
          method: "posawesome.posawesome.api.posapp.get_available_currencies"
        });

        if (r.message) {
          console.log("Received currencies:", r.message);
          
          // Get base currency for reference
          const baseCurrency = this.pos_profile.currency;
          
          // Create simple currency list with just names
          this.available_currencies = r.message.map(currency => {
            return {
              value: currency.name,
              title: currency.name
            };
          });

          // Sort currencies - base currency first, then others alphabetically
          this.available_currencies.sort((a, b) => {
            if (a.value === baseCurrency) return -1;
            if (b.value === baseCurrency) return 1;
            return a.value.localeCompare(b.value);
          });

          // Set default currency if not already set
          if (!this.selected_currency) {
            this.selected_currency = baseCurrency;
          }

          return this.available_currencies;
        }

        return [];
      } catch (error) {
        console.error("Error fetching currencies:", error);
        // Set default currency as fallback
        const defaultCurrency = this.pos_profile.currency;
        this.available_currencies = [{
          value: defaultCurrency,
          title: defaultCurrency
        }];
        this.selected_currency = defaultCurrency;
        return this.available_currencies;
      }
    },

    async update_currency(currency) {
      if (!currency) return;
      if (currency === this.pos_profile.currency) {
        this.exchange_rate = 1;
        // Emit currency update
        this.eventBus.emit("update_currency", {
          currency: currency,
          exchange_rate: 1
        });
        return;
      }
      
      try {
        console.log('Updating currency exchange rate...');
        console.log('Selected:', currency, 'Base:', this.pos_profile.currency, 'Date:', this.posting_date);
        
        // Get rate from selected to base currency
        const response = await frappe.call({
          method: "erpnext.setup.utils.get_exchange_rate",
          args: {
            from_currency: currency,         // Selected currency (e.g. USD)
            to_currency: this.pos_profile.currency,  // Base currency (e.g. PKR)
            transaction_date: this.posting_date || frappe.datetime.nowdate()
          }
        });

        if (response.message) {
          const rate = response.message;
          // Store the rate directly without inverting
          this.exchange_rate = this.flt(rate, 6);
          console.log("Exchange rate updated:", this.exchange_rate);
          
          // Emit currency update
          this.eventBus.emit("update_currency", {
            currency: currency,
            exchange_rate: this.exchange_rate
          });
          
          // Update the currency title in the dropdown to show the rate
          const currencyIndex = this.available_currencies.findIndex(c => c.value === currency);
          if (currencyIndex !== -1) {
            this.available_currencies[currencyIndex].title = `${currency} (1 = ${this.flt(rate, 6)} ${this.pos_profile.currency})`;
            this.available_currencies[currencyIndex].rate = rate;
          }
          
          // Update all item rates based on new exchange rate
          this.update_item_rates();

          // Show success message
          this.eventBus.emit("show_message", {
            title: __(`Exchange rate updated: 1 ${currency} = ${this.flt(rate, 6)} ${this.pos_profile.currency}`),
            color: "success"
          });
        } else {
          throw new Error("No exchange rate returned");
        }
      } catch (error) {
        console.error("Error updating exchange rate:", error);
        // Reset currency selection to base currency
        this.selected_currency = this.pos_profile.currency;
        this.exchange_rate = 1;
        
        // Emit currency update for reset
        this.eventBus.emit("update_currency", {
          currency: this.pos_profile.currency,
          exchange_rate: 1
        });
        
        // Reset the currency title in the dropdown
        const currencyIndex = this.available_currencies.findIndex(c => c.value === currency);
        if (currencyIndex !== -1) {
          this.available_currencies[currencyIndex].title = currency;
          this.available_currencies[currencyIndex].rate = null;
        }
        
        this.eventBus.emit("show_message", {
          title: __(`Error: Could not fetch exchange rate from ${currency} to ${this.pos_profile.currency}. Please set up the exchange rate first.`),
          color: "error"
        });
      }
    },

    update_exchange_rate() {
      if (!this.exchange_rate || this.exchange_rate <= 0) {
        this.exchange_rate = 1;
      }
      
      // Emit currency update
      this.eventBus.emit("update_currency", {
        currency: this.selected_currency || this.pos_profile.currency,
        exchange_rate: this.exchange_rate
      });
      
      this.update_item_rates();
    },

    update_item_rates() {
      console.log('Updating item rates with exchange rate:', this.exchange_rate);

      this.items.forEach(item => {
        // Store original rates if not already stored
        if (!item.base_rate) {
          item.base_rate = item.rate;
          item.base_price_list_rate = item.price_list_rate;
          item.base_discount_amount = item.discount_amount;
        }

        // Convert all monetary values to selected currency
        if (this.selected_currency !== this.pos_profile.currency) {
          // If exchange rate is 285 PKR = 1 USD
          // To convert PKR to USD: divide by exchange rate
          // Example: 100 PKR / 285 = 0.35 USD
          const converted_price = this.flt(item.base_price_list_rate / this.exchange_rate, this.currency_precision);
          const converted_rate = this.flt(item.base_rate / this.exchange_rate, this.currency_precision);
          const converted_discount = this.flt(item.base_discount_amount / this.exchange_rate, this.currency_precision);

          // Ensure we don't set values to 0 if they're just very small
          item.price_list_rate = converted_price < 0.000001 ? 0 : converted_price;
          item.rate = converted_rate < 0.000001 ? 0 : converted_rate;
          item.discount_amount = converted_discount < 0.000001 ? 0 : converted_discount;

          console.log(`Converted rates for ${item.item_code}:`, {
            base_rate: item.base_rate,
            converted_rate: item.rate,
            exchange_rate: this.exchange_rate,
            precision: this.currency_precision
          });
        } else {
          // Restore base currency values
          item.price_list_rate = item.base_price_list_rate;
          item.rate = item.base_rate;
          item.discount_amount = item.base_discount_amount;
        }

        this.calc_item_price(item);
      });
    },

    formatCurrency(value) {
      if (!value) return "0.00";

      // Convert to absolute value for comparison
      const absValue = Math.abs(value);

      // Determine precision based on value size
      let precision;
      if (absValue >= 1) {
        // Normal values use standard precision (2)
        precision = 2;
      } else if (absValue >= 0.01) {
        // Small values between 0.01 and 1 use 4 decimal places
        precision = 4;
      } else {
        // Very small values use higher precision (6)
        precision = 6;
      }

      // Format the number with determined precision
      const formattedValue = this.flt(value, precision).toFixed(precision);

      // Remove trailing zeros after decimal point while keeping at least 2 decimals
      const parts = formattedValue.split('.');
      if (parts.length === 2) {
        const decimalPart = parts[1].replace(/0+$/, '');
        if (decimalPart.length < 2) {
          return `${parts[0]}.${decimalPart.padEnd(2, '0')}`;
        }
        return `${parts[0]}.${decimalPart}`;
      }

      return formattedValue;
    },

    flt(value, precision = null) {
      // Enhanced float handling for small numbers
      if (precision === null) {
        precision = this.float_precision;
      }

      const _value = Number(value);
      if (isNaN(_value)) {
        return 0;
      }

      // Handle very small numbers to prevent them from becoming 0
      if (Math.abs(_value) < 0.000001) {
        return _value;
      }

      return Number((_value || 0).toFixed(precision));
    },

    // Update currency and exchange rate when currency is changed
    async update_currency_and_rate() {
      if (this.selected_currency) {
        const doc = this.get_invoice_doc();
        doc.currency = this.selected_currency;
        
        try {
          const response = await this.update_invoice(doc);
          if (response && response.conversion_rate) {
            this.exchange_rate = response.conversion_rate;
            this.sync_exchange_rate();
          }
        } catch (error) {
          console.error("Error updating currency:", error);
          this.eventBus.emit("show_message", {
            text: "Error updating currency",
            color: "error",
          });
        }
      }
    },

    async update_exchange_rate_on_server() {
      if (this.exchange_rate) {
        const doc = this.get_invoice_doc();
        doc.conversion_rate = this.exchange_rate;
        try {
          await this.update_invoice(doc);
          this.sync_exchange_rate();
        } catch (error) {
          console.error("Error updating exchange rate:", error);
          this.eventBus.emit("show_message", {
            text: "Error updating exchange rate",
            color: "error",
          });
        }
      }
    },

    sync_exchange_rate() {
      if (!this.exchange_rate || this.exchange_rate <= 0) {
        this.exchange_rate = 1;
      }
      
      // Emit currency update
      this.eventBus.emit("update_currency", {
        currency: this.selected_currency || this.pos_profile.currency,
        exchange_rate: this.exchange_rate
      });
      
      this.update_item_rates();
    },

    // Add new rounding function
    roundAmount(amount) {
      // If multi-currency is enabled and selected currency is different from base currency
      if (this.pos_profile.posa_allow_multi_currency && 
          this.selected_currency !== this.pos_profile.currency) {
        // For multi-currency, just keep 2 decimal places without rounding to nearest integer
        return this.flt(amount, 2);
      }
      // For base currency or when multi-currency is disabled, round to nearest integer
      return Math.round(amount);
    },

    // Increase quantity of an item (handles return logic)
    add_one(item) {
      // For returns, we need to add (make more negative)
      if (this.invoiceType === "Return") {
        item.qty++;
      } else {
        item.qty++;
      }
      if (item.qty == 0) {
        this.remove_item(item);
      }
      this.calc_stock_qty(item, item.qty);
      this.$forceUpdate();
    },

    // Decrease quantity of an item (handles return logic)
    subtract_one(item) {
      // For returns, we need to subtract (make less negative)
      if (this.invoiceType === "Return") {
        item.qty--;
      } else {
        item.qty--;
      }
      if (item.qty == 0) {
        this.remove_item(item);
      }
      this.calc_stock_qty(item, item.qty);
      this.$forceUpdate();
    },
  },

  mounted() {
    // Register event listeners for POS profile, items, customer, offers, etc.
    this.eventBus.on("register_pos_profile", (data) => {
      this.pos_profile = data.pos_profile;
      this.customer = data.pos_profile.customer;
      this.pos_opening_shift = data.pos_opening_shift;
      this.stock_settings = data.stock_settings;
      // Increase precision for better handling of small amounts
      this.float_precision = 6;  // Changed from 2 to 6
      this.currency_precision = 6;  // Changed from 2 to 6
      this.invoiceType = this.pos_profile.posa_default_sales_order
        ? "Order"
        : "Invoice";

      // Add this block to handle currency initialization
      if (this.pos_profile.posa_allow_multi_currency) {
        this.fetch_available_currencies().then(() => {
          // Set default currency after currencies are loaded
          this.selected_currency = this.pos_profile.currency;
          this.exchange_rate = 1;
        }).catch(error => {
          console.error("Error initializing currencies:", error);
          this.eventBus.emit("show_message", {
            title: __("Error loading currencies"),
            color: "error"
          });
        });
      }
    });
    this.eventBus.on("add_item", (item) => {
      this.add_item(item);
    });
    this.eventBus.on("update_customer", (customer) => {
      this.customer = customer;
    });
    this.eventBus.on("fetch_customer_details", () => {
      this.fetch_customer_details();
    });
    this.eventBus.on("clear_invoice", () => {
      this.clear_invoice();
    });
    this.eventBus.on("load_invoice", (data) => {
      this.load_invoice(data);
    });
    this.eventBus.on("load_order", (data) => {
      this.new_order(data);
      // this.eventBus.emit("set_pos_coupons", data.posa_coupons);
    });
    this.eventBus.on("set_offers", (data) => {
      this.posOffers = data;
    });
    this.eventBus.on("update_invoice_offers", (data) => {
      this.updateInvoiceOffers(data);
    });
    this.eventBus.on("update_invoice_coupons", (data) => {
      this.posa_coupons = data;
      this.handelOffers();
    });
    this.eventBus.on("set_all_items", (data) => {
      this.allItems = data;
      this.items.forEach((item) => {
        this.update_item_detail(item);
      });
    });
    this.eventBus.on("load_return_invoice", (data) => {
      // Handle loading of return invoice and set all related fields
      console.log("Invoice component received load_return_invoice event with data:", data);
      this.load_invoice(data.invoice_doc);
      // Explicitly mark as return invoice
      this.invoiceType = "Return";
      this.invoiceTypes = ["Return"];
      this.invoice_doc.is_return = 1;
      // Ensure negative values for returns
      if (this.items && this.items.length) {
        this.items.forEach(item => {
          // Ensure item quantities are negative
          if (item.qty > 0) item.qty = -Math.abs(item.qty);
          if (item.stock_qty > 0) item.stock_qty = -Math.abs(item.stock_qty);
        });
      }
      if (data.return_doc) {
        console.log("Return against existing invoice:", data.return_doc.name);
        // Ensure negative discount amounts
        this.discount_amount = data.return_doc.discount_amount > 0 ? 
          -Math.abs(data.return_doc.discount_amount) : 
          data.return_doc.discount_amount;
        this.additional_discount_percentage = data.return_doc.additional_discount_percentage > 0 ?
          -Math.abs(data.return_doc.additional_discount_percentage) :
          data.return_doc.additional_discount_percentage;
        this.return_doc = data.return_doc;
        // Set return_against reference
        this.invoice_doc.return_against = data.return_doc.name;
      } else {
        console.log("Return without invoice reference");
        // For return without invoice, reset discount values
        this.discount_amount = 0;
        this.additional_discount_percentage = 0;
      }
      console.log("Invoice state after loading return:", {
        invoiceType: this.invoiceType,
        is_return: this.invoice_doc.is_return,
        items: this.items.length,
        customer: this.customer
      });
    });
    this.eventBus.on("set_new_line", (data) => {
      this.new_line = data;
    });
    if (this.pos_profile.posa_allow_multi_currency) {
      this.fetch_available_currencies();
    }
    // Listen for reset_posting_date to reset posting date after invoice submission
    this.eventBus.on("reset_posting_date", () => {
      this.posting_date = frappe.datetime.nowdate();
    });
  },
  // Cleanup event listeners before component is destroyed
  beforeUnmount() {
    // Existing cleanup
    this.eventBus.off("register_pos_profile");
    this.eventBus.off("add_item");
    this.eventBus.off("update_customer");
    this.eventBus.off("fetch_customer_details");
    this.eventBus.off("clear_invoice");
    // Cleanup reset_posting_date listener
    this.eventBus.off("reset_posting_date");
  },
  // Register global keyboard shortcuts when component is created
  created() {
    document.addEventListener("keydown", this.shortOpenPayment.bind(this));
    document.addEventListener("keydown", this.shortDeleteFirstItem.bind(this));
    document.addEventListener("keydown", this.shortOpenFirstItem.bind(this));
    document.addEventListener("keydown", this.shortSelectDiscount.bind(this));
  },
  // Remove global keyboard shortcuts when component is unmounted
  unmounted() {
    document.removeEventListener("keydown", this.shortOpenPayment);
    document.removeEventListener("keydown", this.shortDeleteFirstItem);
    document.removeEventListener("keydown", this.shortOpenFirstItem);
    document.removeEventListener("keydown", this.shortSelectDiscount);
  },
  // Vue watchers for reactive data changes
  watch: {
    // Watch for customer change and update related data
    customer() {
      this.close_payments();
      this.eventBus.emit("set_customer", this.customer);
      this.fetch_customer_details();
      this.fetch_customer_balance();
      this.set_delivery_charges();
    },
    // Watch for customer_info change and emit to edit form
    customer_info() {
      this.eventBus.emit("set_customer_info_to_edit", this.customer_info);
    },
    // Watch for expanded row change and update item detail
    expanded(data_value) {
      if (data_value.length > 0) {
        this.update_item_detail(data_value[0]);
      }
    },
    // Watch for discount offer name change and emit
    discount_percentage_offer_name() {
      this.eventBus.emit("update_discount_percentage_offer_name", {
        value: this.discount_percentage_offer_name,
      });
    },
    // Watch for items array changes (deep) and re-handle offers
    items: {
      deep: true,
      handler(items) {
        this.handelOffers();
        this.$forceUpdate();
      },
    },
    // Watch for invoice type change and emit
    invoiceType() {
      this.eventBus.emit("update_invoice_type", this.invoiceType);
    },
    // Watch for additional discount and update percentage accordingly
    additional_discount() {
      if (!this.additional_discount || this.additional_discount == 0) {
        this.additional_discount_percentage = 0;
      } else if (this.pos_profile.posa_use_percentage_discount) {
        // Prevent division by zero which causes NaN
        if (this.Total && this.Total !== 0) {
          this.additional_discount_percentage =
            (this.additional_discount / this.Total) * 100;
        } else {
          this.additional_discount_percentage = 0;
        }
      } else {
        this.additional_discount_percentage = 0;
      }
    },
    // Watch for posting date changes and ensure correct format
    posting_date: {
      handler(newVal) {
        if (!newVal) return;
        // Make sure the date is in YYYY-MM-DD format
        if (typeof newVal === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(newVal)) {
          return; // Already in correct format
        }

        let dateStr;
        if (newVal instanceof Date) {
          const year = newVal.getFullYear();
          const month = String(newVal.getMonth() + 1).padStart(2, '0');
          const day = String(newVal.getDate()).padStart(2, '0');
          dateStr = `${year}-${month}-${day}`;
        } else {
          dateStr = frappe.datetime.nowdate();
        }

        this.posting_date = dateStr;
      },
      immediate: true
    },
  },
};
</script>

<style scoped>
/* Style for selected checkbox button */
.v-checkbox-btn.v-selected {
  background-color: #4CAF50 !important;
  color: white;
}

/* Bottom border for elements */
.border_line_bottom {
  border-bottom: 1px solid lightgray;
}

/* Disable pointer events for elements */
.disable-events {
  pointer-events: none;
}

/* Style for customer balance field */
.balance-field {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

/* Style for balance value text */
.balance-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #d32f2f;
  margin-left: 5px;
}

/* Styles for date picker buttons */
.v-date-picker .v-btn {
  min-width: 80px !important;
  margin: 0 4px !important;
  text-transform: none !important;
  font-weight: 500 !important;
}

/* Style for text variant date picker button */
.v-date-picker .v-btn--variant-text {
  padding: 0 12px !important;
}

/* Spacer inside date picker */
.v-date-picker .v-spacer {
  flex: 1 1 auto !important;
}

/* Updated style for date picker action buttons */
.date-action-btn {
  min-width: 64px !important;
  height: 36px !important;
  margin: 4px !important;
  padding: 0 16px !important;
  text-transform: none !important;
  font-weight: 500 !important;
  font-size: 14px !important;
  letter-spacing: 0.25px !important;
}

/* Card style for date picker */
.v-date-picker {
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

/* Actions section in date picker card */
.v-date-picker .v-card-actions {
  padding: 8px !important;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}

/* Red border and label for return mode card */
.return-mode {
  border: 2px solid #ff5252 !important;
  position: relative;
}

/* Label for return mode card */
.return-mode::before {
  content: 'RETURN';
  position: absolute;
  top: 0;
  right: 0;
  background-color: #ff5252;
  color: white;
  padding: 4px 12px;
  font-weight: bold;
  border-bottom-left-radius: 8px;
  z-index: 1;
}
</style>