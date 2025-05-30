<div align="center">
    <img src="https://frappecloud.com/files/pos.png" height="128">
    <h2>POS AWESOME</h2>
</div>

#### An open-source Point of Sale for [Erpnext](https://github.com/frappe/erpnext) using [Vue.js](https://github.com/vuejs/vue) and [Vuetify](https://github.com/vuetifyjs/vuetify) (VERSION 15 Support)

---

### Main Features

1. Supports Erpnext Version 15
2. Supports Multi-Currency Transactions.
    Customers can be invoiced in different currencies
    Exchange Rate is fetched automatically based on selected currency
    Invoices made with posawesome display Grand Total in both base and selected currency in erpnext.
    
3. User-friendly and provides a good user experience and speed of use
4. The cashier can either use list view or card view during sales transactions. Card view shows the images of the items
5. Supports enqueue invoice submission after printing the receipt for faster processing
6. Supports batch & serial numbering
7. Supports batch-based pricing
8. Supports UOM-specific barcode and pricing
9. Supports sales of scale (weighted) products
10. Ability to make returns from POS
11. Supports Making returns for either cash or customer credit
12. Supports using customer credit notes for payment
13. Supports credit sales
14. Allows the user to choose a due date for credit sales
15. Supports customer loyalty points
16. Shortcut keys
17. Supports Customer Discount
18. Supports POS Offers
19. Auto-apply batches for bundle items
20. Search and add items by Serial Number
21. Create Sales Orders from POS directly
22. Supports template items with variants
23. Supports multiple languages
24. Supports Mpesa mobile payment
25. POS Coupons
26. Supports Referral Code
27. Supports Customer and Customer Group price list
28. Supports Sales Person
29. Supports Delivery Charges
30. Search and add items by Batch Number
31. Accept new payments from customers against existing invoices
32. Payments Reconciliation
33. A lot more bug fixes from the version 14

### How to Install

#### Self Hosting:

1. `bench get-app https://github.com/defendicon/POS-Awesome-V15`
2. `bench setup requirements`
3. `bench build --app posawesome`
4. `bench restart`
5. `bench --site [your.site.name] install-app posawesome`
6. `bench --site [your.site.name] migrate`

---

### How To Use:

[POS Awesome Wiki](https://github.com/yrestom/POS-Awesome/wiki)

---

### Shortcuts:

- `CTRL or CMD + S` open payments
- `CTRL or CMD + X` submit payments
- `CTRL or CMD + D` remove the first item from the top
- `CTRL or CMD + A` expand the first item from the top
- `CTRL or CMD + E` focus on discount field

---

### Dependencies:

- [Frappe](https://github.com/frappe/frappe)
- [Erpnext](https://github.com/frappe/erpnext)
- [Vue.js](https://github.com/vuejs/vue)
- [Vuetify.js](https://github.com/vuetifyjs/vuetify)

---

### Contributing

1. [Issue Guidelines](https://github.com/frappe/erpnext/wiki/Issue-Guidelines)
2. [Pull Request Requirements](https://github.com/frappe/erpnext/wiki/Contribution-Guidelines)

---

### License

GNU/General Public License (see [license.txt](https://github.com/yrestom/POS-Awesome/blob/master/license.txt))

The POS Awesome code is licensed as GNU General Public License (v3)
