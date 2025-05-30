<template>
  <v-row justify="center">
    <v-dialog v-model="invoicesDialog" max-width="800px" min-width="800px">
      <v-card>
        <v-card-title>
          <span class="text-h5 text-primary">{{
            __('Select Return Invoice')
          }}</span>
        </v-card-title>
        <v-container>
          <!-- Invoice ID and Date Range search -->
          <v-row class="mb-2">
            <v-col cols="12">
              <v-alert
                dense
                type="info"
                text
                outlined
                v-if="!from_date && !to_date"
              >
                <small>{{ __('Use date range to search for older invoices') }}</small>
              </v-alert>
            </v-col>
          </v-row>
          <v-row class="mb-3">
            <v-col cols="12" sm="6">
              <v-text-field color="primary" :label="frappe._('Invoice ID')" bg-color="white" hide-details
                v-model="invoice_name" density="compact" clearable></v-text-field>
            </v-col>
            <v-col cols="12" sm="3">
              <v-menu
                v-model="fromDateMenu"
                :close-on-content-click="false"
                transition="scale-transition"
                offset-y
                min-width="auto"
              >
                <template v-slot:activator="{ props }">
                  <v-text-field
                    v-model="from_date_formatted"
                    :label="frappe._('From Date')"
                    prepend-icon="mdi-calendar"
                    readonly
                    v-bind="props"
                    clearable
                    @click:clear="clearFromDate"
                    hide-details
                    dense
                    color="primary"
                    outlined
                  ></v-text-field>
                </template>
                <v-date-picker
                  v-model="from_date"
                  no-title
                  @update:model-value="fromDateMenu = false; formatFromDate();"
                ></v-date-picker>
              </v-menu>
            </v-col>
            <v-col cols="12" sm="3">
              <v-menu
                v-model="toDateMenu"
                :close-on-content-click="false"
                transition="scale-transition"
                offset-y
                min-width="auto"
              >
                <template v-slot:activator="{ props }">
                  <v-text-field
                    v-model="to_date_formatted"
                    :label="frappe._('To Date')"
                    prepend-icon="mdi-calendar"
                    readonly
                    v-bind="props"
                    clearable
                    @click:clear="clearToDate"
                    hide-details
                    dense
                    color="primary"
                    outlined
                  ></v-text-field>
                </template>
                <v-date-picker
                  v-model="to_date"
                  no-title
                  @update:model-value="toDateMenu = false; formatToDate();"
                ></v-date-picker>
              </v-menu>
            </v-col>
          </v-row>

          <!-- Customer search fields -->
          <v-row class="mb-2">
            <v-col cols="12" sm="6">
              <v-text-field 
                color="primary" 
                :label="frappe._('Customer Name')" 
                bg-color="white" 
                hide-details
                v-model="customer_name" 
                density="compact" 
                clearable
              ></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field 
                color="primary" 
                :label="frappe._('Customer ID')" 
                bg-color="white" 
                hide-details
                v-model="customer_id" 
                density="compact" 
                clearable
              ></v-text-field>
            </v-col>
          </v-row>
          <v-row class="mb-3">
            <v-col cols="12" sm="6">
              <v-text-field 
                color="primary" 
                :label="frappe._('Mobile Number')" 
                bg-color="white" 
                hide-details
                v-model="mobile_no" 
                density="compact" 
                clearable
              ></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field 
                color="primary" 
                :label="frappe._('Tax ID')" 
                bg-color="white" 
                hide-details
                v-model="tax_id" 
                density="compact" 
                clearable
              ></v-text-field>
            </v-col>
          </v-row>

          <!-- Amount Filter -->
          <v-row class="mb-3">
            <v-col cols="12" sm="6">
              <v-text-field 
                color="primary" 
                :label="frappe._('Minimum Amount')" 
                bg-color="white" 
                hide-details
                v-model="min_amount" 
                density="compact" 
                clearable
                type="number"
                min="0"
                placeholder="0"
              ></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field 
                color="primary" 
                :label="frappe._('Maximum Amount')" 
                bg-color="white" 
                hide-details
                v-model="max_amount" 
                density="compact" 
                clearable
                type="number"
                min="0"
                placeholder="No limit"
              ></v-text-field>
            </v-col>
          </v-row>
          
          <v-row>
            <v-col cols="12" class="pt-0 pb-0">
              <v-divider></v-divider>
            </v-col>
          </v-row>

          <!-- Action buttons -->
          <v-row class="mt-2 mb-2">
            <v-spacer></v-spacer>
            <v-btn variant="text" class="ml-2" color="primary" theme="dark" @click="search_invoices">
              <v-icon left>mdi-magnify</v-icon>
              {{ __('Search') }}
            </v-btn>
            <v-btn variant="text" class="ml-2" color="warning" theme="dark" @click="clear_search">
              <v-icon left>mdi-refresh</v-icon>
              {{ __('Clear') }}
            </v-btn>
            <v-btn v-if="pos_profile.posa_allow_return_without_invoice == 1" variant="text" class="ml-2" color="secondary" theme="dark" @click="return_without_invoice">
              {{ __('Return without Invoice') }}
            </v-btn>
          </v-row>

          <!-- Results -->
          <v-row>
            <v-col cols="12" class="pa-0 mt-1" v-if="dialog_data && dialog_data.length > 0">
              <v-data-table 
                :headers="headers" 
                :items="dialog_data" 
                item-key="name" 
                class="elevation-1" 
                show-select
                v-model="selected" 
                select-strategy="single" 
                return-object
                :footer-props="{
                  'items-per-page-options': [10, 25, 50, 100],
                  'items-per-page-text': 'Invoices per page'
                }"
                :items-per-page="25"
              >
                <template v-slot:item.posting_date="{ item }">
                  {{ formatDateDisplay(item.posting_date) }}
                </template>
                <template v-slot:item.grand_total="{ item }">
                  {{ currencySymbol(item.currency) }}
                  {{ formatCurrency(item.grand_total) }}
                </template>
              </v-data-table>

              <!-- Load More button at the bottom of results -->
              <div class="text-center mt-3" v-if="has_more_invoices">
                <v-btn 
                  color="primary" 
                  text 
                  outlined 
                  :loading="loading_more" 
                  @click="load_more_invoices"
                >
                  {{ __('Load More Invoices') }}
                </v-btn>
              </div>
            </v-col>
            <v-col cols="12" class="text-center" v-else-if="searched_once && (!dialog_data || dialog_data.length === 0)">
              <v-alert type="warning" text>
                {{ __('No invoices found. Try different search criteria.') }}
              </v-alert>
            </v-col>
          </v-row>
        </v-container>
        <v-card-actions class="mt-1">
          <v-spacer></v-spacer>
          <v-btn color="error mx-2" theme="dark" @click="close_dialog">{{ __('Close') }}</v-btn>
          <v-btn v-if="selected.length" color="success" theme="dark" @click="submit_dialog">{{ __('Select') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-row>
</template>

<script>
import format from '../../format';

export default {
  mixins: [format],
  data: () => ({
    invoicesDialog: false,
    singleSelect: true,
    selected: [],
    dialog_data: [],
    company: '',
    invoice_name: '',
    customer_name: '',
    customer_id: '',
    mobile_no: '',
    tax_id: '',
    from_date: null,
    to_date: null,
    from_date_formatted: null,
    to_date_formatted: null,
    min_amount: '',
    max_amount: '',
    fromDateMenu: false,
    toDateMenu: false,
    pos_profile: '',
    page: 1,
    has_more_invoices: false,
    loading_more: false,
    searched_once: false,
    current_search_params: null,
    headers: [
      {
        title: __('Customer'),
        value: 'customer',
        align: 'start',
        sortable: true,
      },
      {
        title: __('Date'),
        align: 'start',
        sortable: true,
        value: 'posting_date',
      },
      {
        title: __('Invoice'),
        value: 'name',
        align: 'start',
        sortable: true,
      },
      {
        title: __('Amount'),
        value: 'grand_total',
        align: 'end',
        sortable: false,
      },
    ],
  }),
  watch: {
    from_date() {
      this.formatFromDate();
    },
    to_date() {
      this.formatToDate();
    }
  },
  methods: {
    formatDateDisplay(dateStr) {
      if (!dateStr) return '';
      try {
        // Convert YYYY-MM-DD to DD/MM/YYYY
        const parts = dateStr.split('-');
        if (parts.length === 3) {
          return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }
      } catch (error) {
        console.error("Error formatting date:", error);
      }
      return dateStr;
    },
    formatFromDate() {
      if (this.from_date) {
        try {
          let dateString = '';
          
          // Handle Date object
          if (typeof this.from_date === 'object' && this.from_date instanceof Date) {
            const day = String(this.from_date.getDate()).padStart(2, '0');
            const month = String(this.from_date.getMonth() + 1).padStart(2, '0');
            const year = this.from_date.getFullYear();
            dateString = `${day}/${month}/${year}`;
          }
          // Handle string in YYYY-MM-DD format
          else if (typeof this.from_date === 'string' && this.from_date.includes('-')) {
            const parts = this.from_date.split('-');
            if (parts.length === 3) {
              dateString = `${parts[2]}/${parts[1]}/${parts[0]}`;
            } else {
              dateString = this.from_date;
            }
          } 
          // Handle any other format - just display as is
          else {
            dateString = String(this.from_date);
          }
          
          this.from_date_formatted = dateString;
        } catch (error) {
          console.error("Error formatting from_date:", error);
          this.from_date_formatted = String(this.from_date);
        }
      } else {
        this.from_date_formatted = null;
      }
    },
    formatToDate() {
      if (this.to_date) {
        try {
          let dateString = '';
          
          // Handle Date object
          if (typeof this.to_date === 'object' && this.to_date instanceof Date) {
            const day = String(this.to_date.getDate()).padStart(2, '0');
            const month = String(this.to_date.getMonth() + 1).padStart(2, '0');
            const year = this.to_date.getFullYear();
            dateString = `${day}/${month}/${year}`;
          }
          // Handle string in YYYY-MM-DD format
          else if (typeof this.to_date === 'string' && this.to_date.includes('-')) {
            const parts = this.to_date.split('-');
            if (parts.length === 3) {
              dateString = `${parts[2]}/${parts[1]}/${parts[0]}`;
            } else {
              dateString = this.to_date;
            }
          }
          // Handle any other format - just display as is
          else {
            dateString = String(this.to_date);
          }
          
          this.to_date_formatted = dateString;
        } catch (error) {
          console.error("Error formatting to_date:", error);
          this.to_date_formatted = String(this.to_date);
        }
      } else {
        this.to_date_formatted = null;
      }
    },
    clearFromDate() {
      this.from_date = null;
      this.from_date_formatted = null;
    },
    clearToDate() {
      this.to_date = null;
      this.to_date_formatted = null;
    },
    close_dialog() {
      this.invoicesDialog = false;
    },
    clear_search() {
      this.invoice_name = '';
      this.customer_name = '';
      this.customer_id = '';
      this.mobile_no = '';
      this.tax_id = '';
      this.from_date = null;
      this.to_date = null;
      this.from_date_formatted = null;
      this.to_date_formatted = null;
      this.min_amount = '';
      this.max_amount = '';
      this.dialog_data = [];
      this.page = 1;
      this.has_more_invoices = false;
      this.searched_once = false;
    },
    search_invoices_by_enter(e) {
      if (e.keyCode === 13) {
        this.search_invoices();
      }
    },
    search_invoices() {
      this.page = 1;
      this.dialog_data = [];
      this.perform_search();
    },
    perform_search() {
      const vm = this;
      vm.loading_more = true;
      
      // Format dates for API call in YYYY-MM-DD format
      let formattedFromDate = null;
      let formattedToDate = null;
      
      if (vm.from_date) {
        if (typeof vm.from_date === 'object' && vm.from_date instanceof Date) {
          // Format Date object to YYYY-MM-DD
          formattedFromDate = [
            vm.from_date.getFullYear(),
            String(vm.from_date.getMonth() + 1).padStart(2, '0'),
            String(vm.from_date.getDate()).padStart(2, '0')
          ].join('-');
        } else if (typeof vm.from_date === 'string') {
          if (vm.from_date.includes('/')) {
            // Convert DD/MM/YYYY to YYYY-MM-DD
            const parts = vm.from_date.split('/');
            if (parts.length === 3) {
              formattedFromDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
          } else if (vm.from_date.includes('-')) {
            // Already in YYYY-MM-DD format
            formattedFromDate = vm.from_date;
          } else {
            // Invalid format, skip date filter
            formattedFromDate = null;
          }
        }
      }
      
      if (vm.to_date) {
        if (typeof vm.to_date === 'object' && vm.to_date instanceof Date) {
          // Format Date object to YYYY-MM-DD
          formattedToDate = [
            vm.to_date.getFullYear(),
            String(vm.to_date.getMonth() + 1).padStart(2, '0'),
            String(vm.to_date.getDate()).padStart(2, '0')
          ].join('-');
        } else if (typeof vm.to_date === 'string') {
          if (vm.to_date.includes('/')) {
            // Convert DD/MM/YYYY to YYYY-MM-DD
            const parts = vm.to_date.split('/');
            if (parts.length === 3) {
              formattedToDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
          } else if (vm.to_date.includes('-')) {
            // Already in YYYY-MM-DD format
            formattedToDate = vm.to_date;
          } else {
            // Invalid format, skip date filter
            formattedToDate = null;
          }
        }
      }
      
      // Process amount filters
      let minAmount = vm.min_amount ? parseFloat(vm.min_amount) : null;
      let maxAmount = vm.max_amount ? parseFloat(vm.max_amount) : null;
      
      // Save current search parameters for "load more" functionality
      this.current_search_params = {
        invoice_name: vm.invoice_name,
        customer_name: vm.customer_name,
        customer_id: vm.customer_id,
        mobile_no: vm.mobile_no,
        tax_id: vm.tax_id,
        from_date: formattedFromDate,
        to_date: formattedToDate,
        min_amount: minAmount,
        max_amount: maxAmount,
        company: vm.company,
        page: vm.page
      };
      
      frappe.call({
        method: 'posawesome.posawesome.api.posapp.search_invoices_for_return',
        args: this.current_search_params,
        callback: function (r) {
          vm.loading_more = false;
          vm.searched_once = true;
          
          if (r.message) {
            // If this is page 1, replace data, otherwise append
            if (vm.page === 1) {
              vm.dialog_data = r.message.invoices;
            } else {
              vm.dialog_data = [...vm.dialog_data, ...r.message.invoices];
            }
            
            // Set flag if there are more invoices to load
            vm.has_more_invoices = r.message.has_more;
          } else {
            vm.dialog_data = [];
            vm.has_more_invoices = false;
            vm.eventBus.emit('show_message', {
              title: __('No invoices found'),
              color: 'warning',
            });
          }
        },
        error: function(err) {
          vm.loading_more = false;
          console.error("Error searching invoices:", err);
          vm.eventBus.emit('show_message', {
            title: __('Error searching invoices'),
            color: 'error',
          });
        }
      });
    },
    load_more_invoices() {
      this.page += 1;
      this.perform_search();
    },
    return_without_invoice() {
      console.log('Starting return without invoice flow');
      const invoice_doc = {};
      invoice_doc.items = [];
      invoice_doc.is_return = 1;
      const data = { invoice_doc };
      console.log('Emitting load_return_invoice event with data:', data);
      this.eventBus.emit('load_return_invoice', data);
      this.invoicesDialog = false;
    },
    submit_dialog() {
      if (this.selected.length > 0) {
        console.log('Starting return with invoice flow');
        const return_doc = this.selected[0];
        const invoice_doc = {};
        const items = [];
        
        console.log('Original return doc:', return_doc);
        
        return_doc.items.forEach((item) => {
          const new_item = { ...item };
          // Make sure quantities are negative for returns
          new_item.qty = item.qty > 0 ? item.qty * -1 : item.qty;
          new_item.stock_qty = item.stock_qty > 0 ? item.stock_qty * -1 : item.stock_qty;
          new_item.amount = item.amount > 0 ? item.amount * -1 : item.amount;
          items.push(new_item);
        });
        
        invoice_doc.items = items;
        invoice_doc.is_return = 1;
        invoice_doc.return_against = return_doc.name;
        invoice_doc.customer = return_doc.customer;
        
        // Make sure grand_total is negative for returns
        if (return_doc.grand_total > 0) {
          invoice_doc.grand_total = return_doc.grand_total * -1;
        } else {
          invoice_doc.grand_total = return_doc.grand_total;
        }
        
        // These fields ensure proper return handling
        invoice_doc.update_stock = 1;
        invoice_doc.pos_profile = this.pos_profile.name;
        invoice_doc.company = this.company;
        
        const data = { invoice_doc, return_doc };
        console.log('Emitting load_return_invoice event with data:', data);
        
        this.eventBus.emit('load_return_invoice', data);
        this.invoicesDialog = false;
      }
    },
  },
  created: function () {
    this.eventBus.on('open_returns', (data) => {
      this.invoicesDialog = true;
      this.company = data;
      this.invoice_name = '';
      this.customer_name = '';
      this.customer_id = '';
      this.mobile_no = '';
      this.tax_id = '';
      this.from_date = null;
      this.to_date = null;
      this.from_date_formatted = null;
      this.to_date_formatted = null;
      this.min_amount = '';
      this.max_amount = '';
      this.dialog_data = [];
      this.selected = [];
      this.page = 1;
      this.has_more_invoices = false;
      this.searched_once = false;
    });

    this.eventBus.on('register_pos_profile', (data) => {
      this.pos_profile = data.pos_profile;
    });
  },
  beforeUnmount() {
    this.eventBus.off('open_returns');
    this.eventBus.off('register_pos_profile');
  },
};
</script>
