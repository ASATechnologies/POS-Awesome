<template>
  <div>
    <v-card class="selection mx-auto bg-grey-lighten-5 mt-3" style="max-height: 75vh; height: 75vh">
      <v-progress-linear :active="loading" :indeterminate="loading" absolute :location="top"
        color="info"></v-progress-linear>
      <v-row class="items px-2 py-1">
        <v-col class="pb-0 mb-2">
          <v-text-field density="compact" clearable autofocus variant="solo" color="primary"
            :label="frappe._('Search Items')" hint="Search by item code, serial number, batch no or barcode"
            bg-color="white" hide-details v-model="debounce_search" @keydown.esc="esc_event"
            @keydown.enter="search_onchange" @click:clear="clearSearch"
            prepend-inner-icon="mdi-magnify"
            @focus="handleItemSearchFocus" ref="debounce_search"></v-text-field>
        </v-col>
        <v-col cols="3" class="pb-0 mb-2" v-if="pos_profile.posa_input_qty">
          <v-text-field density="compact" variant="solo" color="primary" :label="frappe._('QTY')" bg-color="white"
            hide-details v-model.number="qty" type="number" @keydown.enter="enter_event"
            @keydown.esc="esc_event"></v-text-field>
        </v-col>
        <v-col cols="2" class="pb-0 mb-2" v-if="pos_profile.posa_new_line">
          <v-checkbox v-model="new_line" color="accent" value="true" label="NLine" density="default"
            hide-details></v-checkbox>
        </v-col>
        <v-col cols="12" class="pt-0 mt-0">
          <div fluid class="items" v-if="items_view == 'card'">
            <v-row density="default" class="overflow-y-auto" style="max-height: 67vh">
              <v-col v-for="(item, idx) in filtered_items" :key="idx" xl="2" lg="3" md="6" sm="6" cols="6"
                min-height="50">
                <v-card hover="hover" @click="add_item(item)">
                  <v-img :src="item.image ||
                    '/assets/posawesome/js/posapp/components/pos/placeholder-image.png'
                    " class="text-white align-end" gradient="to bottom, rgba(0,0,0,0), rgba(0,0,0,0.4)" height="100px">
                    <v-card-text v-text="item.item_name" class="text-caption px-1 pb-0"></v-card-text>
                  </v-img>
                  <v-card-text class="text--primary pa-1">
                    <div class="text-caption text-primary">
                      {{ currencySymbol(pos_profile.currency) || "" }}
                      {{ format_currency(item.rate, pos_profile.currency, 4) }}
                    </div>
                    <div v-if="pos_profile.posa_allow_multi_currency && selected_currency !== pos_profile.currency" class="text-caption text-success">
                      {{ currencySymbol(selected_currency) || "" }}
                      {{ format_currency(getConvertedRate(item), selected_currency, 4) }}
                    </div>
                    <div class="text-caption golden--text">
                      {{ format_number(item.actual_qty, 4) || 0 }}
                      {{ item.stock_uom || "" }}
                    </div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
          </div>
          <div fluid class="items" v-if="items_view == 'list'">
            <div class="my-0 py-0 overflow-y-auto" style="max-height: 65vh">
              <v-data-table :headers="getItemsHeaders()" :items="filtered_items" item-key="item_code" item-value="item-"
                class="elevation-0 sleek-data-table" :items-per-page="itemsPerPage" hide-default-footer @click:row="click_item_row">
                <template v-slot:item.rate="{ item }">
                  <div>
                    <div class="text-primary">{{ currencySymbol(pos_profile.currency) }}
                      {{ format_currency(item.rate, pos_profile.currency, 4) }}</div>
                    <div v-if="pos_profile.posa_allow_multi_currency && selected_currency !== pos_profile.currency" class="text-success">
                      {{ currencySymbol(selected_currency) }}
                      {{ format_currency(getConvertedRate(item), selected_currency, 4) }}
                    </div>
                  </div>
                </template>
                <template v-slot:item.actual_qty="{ item }">
                  <span class="golden--text">{{ format_number(item.actual_qty, 4) }}</span>
                </template>
              </v-data-table>
            </div>
          </div>
        </v-col>
      </v-row>
    </v-card>
    <v-card class="cards mb-0 mt-3 pa-2 bg-grey-lighten-5">
      <v-row no-gutters align="center" justify="center">
        <v-col cols="12">
          <v-select :items="items_group" :label="frappe._('Items Group')" density="compact" variant="solo"
            hide-details v-model="item_group"></v-select>
        </v-col>
        <v-col cols="3" class="mt-1">
          <v-btn-toggle v-model="items_view" color="primary" group density="compact" rounded>
            <v-btn size="small" value="list">{{ __("List") }}</v-btn>
            <v-btn size="small" value="card">{{ __("Card") }}</v-btn>
          </v-btn-toggle>
        </v-col>
        <v-col cols="4" class="mt-2">
          <v-btn size="small" block color="primary" variant="text" @click="show_coupons">{{ couponsCount }} {{
            __("Coupons")
            }}</v-btn>
        </v-col>
        <v-col cols="5" class="mt-2">
          <v-btn size="small" block color="primary" variant="text" @click="show_offers">{{ offersCount }} {{
            __("Offers") }}
            : {{ appliedOffersCount }}
            {{ __("Applied") }}</v-btn>
        </v-col>
      </v-row>
    </v-card>
  </div>
</template>

<script>

import format from "../../format";
import _ from "lodash";
export default {
  mixins: [format],
  data: () => ({
    pos_profile: "",
    flags: {},
    items_view: "list",
    item_group: "ALL",
    loading: false,
    items_group: ["ALL"],
    items: [],
    search: "",
    first_search: "",
    search_backup: "",
    itemsPerPage: 1000,
    offersCount: 0,
    appliedOffersCount: 0,
    couponsCount: 0,
    appliedCouponsCount: 0,
    customer_price_list: null,
    customer: null,
    new_line: false,
    qty: 1,
    refresh_interval: null,
    currentRequest: null,
    abortController: null,
    items_loaded: false,
    selected_currency: "",
    exchange_rate: 1,
  }),

  watch: {
    filtered_items(new_value, old_value) {
      if (!this.pos_profile.pose_use_limit_search) {
        if (new_value.length != old_value.length) {
          this.update_items_details(new_value);
        }
      }
    },
    customer() {
      if (this.items_loaded && this.filtered_items && this.filtered_items.length > 0) {
        this.update_items_details(this.filtered_items);
      } else {
        this.get_items();
      }
    },
    new_line() {
      this.eventBus.emit("set_new_line", this.new_line);
    },
  },

  methods: {
    show_offers() {
      this.eventBus.emit("show_offers", "true");
    },
    show_coupons() {
      this.eventBus.emit("show_coupons", "true");
    },
    get_items() {
      if (!this.pos_profile) {
        console.error("No POS Profile");
        return;
      }
      
      // If items are already loaded and it's not a specific search or customer change, don't reload
      if (this.items_loaded && !this.first_search && !this.pos_profile.pose_use_limit_search) {
        console.info("Items already loaded, skipping reload");
        // Still update quantities for displayed items
        if (this.filtered_items && this.filtered_items.length > 0) {
          this.update_items_details(this.filtered_items);
        }
        return;
      }
      
      const vm = this;
      this.loading = true;
      let search = this.get_search(this.first_search);
      let gr = "";
      let sr = "";
      if (search) {
        sr = search;
      }
      if (vm.item_group != "ALL") {
        gr = vm.item_group.toLowerCase();
      }
      if (
        vm.pos_profile.posa_local_storage &&
        localStorage.items_storage &&
        !vm.pos_profile.pose_use_limit_search
      ) {
        vm.items = JSON.parse(localStorage.getItem("items_storage"));
        this.eventBus.emit("set_all_items", vm.items);
        vm.loading = false;
        vm.items_loaded = true;
        
        // Even when loading from localStorage, refresh the quantities
        setTimeout(() => {
          if (vm.filtered_items && vm.filtered_items.length > 0) {
            vm.update_items_details(vm.filtered_items);
          }
        }, 300);
      }
      frappe.call({
        method: "posawesome.posawesome.api.posapp.get_items",
        args: {
          pos_profile: vm.pos_profile,
          price_list: vm.customer_price_list,
          item_group: gr,
          search_value: sr,
          customer: vm.customer,
        },
        callback: function (r) {
          if (r.message) {
            vm.items = r.message;
            vm.eventBus.emit("set_all_items", vm.items);
            vm.loading = false;
            vm.items_loaded = true;
            console.info("Items Loaded");
            vm.$nextTick(() => {
              if(vm.search) vm.search_onchange();
            });
            
            // Always refresh quantities after items are loaded
            setTimeout(() => {
              if (vm.filtered_items && vm.filtered_items.length > 0) {
                vm.update_items_details(vm.filtered_items);
              }
            }, 300);
            
            if (
              vm.pos_profile.posa_local_storage &&
              !vm.pos_profile.pose_use_limit_search
            ) {
              localStorage.setItem("items_storage", "");
              try {
                localStorage.setItem(
                  "items_storage",
                  JSON.stringify(r.message)
                );
              } catch (e) {
                console.error(e);
              }
            }
            if (vm.pos_profile.pose_use_limit_search) {
              vm.enter_event();
            }
          }
        },
      });
    },
    get_items_groups() {
      if (!this.pos_profile) {
        console.log("No POS Profile");
        return;
      }
      if (this.pos_profile.item_groups.length > 0) {
        this.pos_profile.item_groups.forEach((element) => {
          if (element.item_group !== "All Item Groups") {
            this.items_group.push(element.item_group);
          }
        });
      } else {
        const vm = this;
        frappe.call({
          method: "posawesome.posawesome.api.posapp.get_items_groups",
          args: {},
          callback: function (r) {
            if (r.message) {
              r.message.forEach((element) => {
                vm.items_group.push(element.name);
              });
            }
          },
        });
      }
    },
    getItemsHeaders() {
      const items_headers = [
        {
          title: __("Name"),
          align: "start",
          sortable: true,
          key: "item_name",
        },
        {
          title: __("Code"),
          align: "start",
          sortable: true,
          key: "item_code",
        },
        { title: __("Rate"), key: "rate", align: "start" },
        { title: __("Available QTY"), key: "actual_qty", align: "start" },
        { title: __("UOM"), key: "stock_uom", align: "start" },
      ];
      if (!this.pos_profile.posa_display_item_code) {
        items_headers.splice(1, 1);
      }

      return items_headers;
    },
    click_item_row(event, { item }) {
      this.add_item(item)
    },
    add_item(item) {
      item = { ...item };
      if (item.has_variants) {
        this.eventBus.emit("open_variants_model", item, this.items);
      } else {
        if (item.actual_qty === 0 && this.pos_profile.posa_display_items_in_stock) {
          this.eventBus.emit("show_message", {
            title: `No stock available for ${item.item_name}`,
            color: "warning",
          });
          this.update_items_details([item]);
          return;
        }
        
        // Ensure UOMs are initialized before adding the item
        if (!item.item_uoms || item.item_uoms.length === 0) {
          // If UOMs are not available, fetch them first
          this.update_items_details([item]);
          
          // Add stock UOM as fallback
          if (!item.item_uoms || item.item_uoms.length === 0) {
            item.item_uoms = [{ uom: item.stock_uom, conversion_factor: 1.0 }];
          }
        }
        
        // Convert rate if multi-currency is enabled
        if (this.pos_profile.posa_allow_multi_currency && 
            this.selected_currency !== this.pos_profile.currency) {
          // Store original rate as base_rate
          item.base_rate = item.rate;
          item.base_price_list_rate = item.price_list_rate;
          
          // Set converted rates
          item.rate = this.getConvertedRate(item);
          item.price_list_rate = this.getConvertedRate(item);
          
          // Set currency
          item.currency = this.selected_currency;
        }

        if (!item.qty || item.qty === 1) {
          item.qty = Math.abs(this.qty);
        }
        this.eventBus.emit("add_item", item);
        this.qty = 1;
      }
    },
    enter_event() {
      let match = false;
      if (!this.filtered_items.length || !this.first_search) {
        return;
      }
      const qty = this.get_item_qty(this.first_search);
      const new_item = { ...this.filtered_items[0] };
      new_item.qty = flt(qty);
      new_item.item_barcode.forEach((element) => {
        if (this.search == element.barcode) {
          new_item.uom = element.posa_uom;
          match = true;
        }
      });
      if (
        !new_item.to_set_serial_no &&
        new_item.has_serial_no &&
        this.pos_profile.posa_search_serial_no
      ) {
        new_item.serial_no_data.forEach((element) => {
          if (this.search && element.serial_no == this.search) {
            new_item.to_set_serial_no = this.first_search;
            match = true;
          }
        });
      }
      if (this.flags.serial_no) {
        new_item.to_set_serial_no = this.flags.serial_no;
      }
      if (
        !new_item.to_set_batch_no &&
        new_item.has_batch_no &&
        this.pos_profile.posa_search_batch_no
      ) {
        new_item.batch_no_data.forEach((element) => {
          if (this.search && element.batch_no == this.search) {
            new_item.to_set_batch_no = this.first_search;
            new_item.batch_no = this.first_search;
            match = true;
          }
        });
      }
      if (this.flags.batch_no) {
        new_item.to_set_batch_no = this.flags.batch_no;
      }
      if (match) {
        this.add_item(new_item);
        this.flags.serial_no = null;
        this.flags.batch_no = null;
        this.qty = 1;
        this.$refs.debounce_search.focus();
      }
    },
    search_onchange: _.debounce(function(newSearchTerm) {
        const vm = this;
        if(newSearchTerm) vm.search = newSearchTerm;
        
        if (vm.pos_profile.pose_use_limit_search) {
            vm.get_items();
        } else {
            // Save the current filtered items before search to maintain quantity data
            const current_items = [...vm.filtered_items];
            if(vm.search && vm.search.length >=3) {
              vm.enter_event();
            }
            
            // After search, update quantities for newly filtered items
            if (vm.filtered_items && vm.filtered_items.length > 0) {
                setTimeout(() => {
                    vm.update_items_details(vm.filtered_items);
                }, 300);
            }
        }
    }, 300),
    get_item_qty(first_search) {
      let scal_qty = Math.abs(this.qty);
      if (first_search.startsWith(this.pos_profile.posa_scale_barcode_start)) {
        let pesokg1 = first_search.substr(7, 5);
        let pesokg;
        if (pesokg1.startsWith("0000")) {
          pesokg = "0.00" + pesokg1.substr(4);
        } else if (pesokg1.startsWith("000")) {
          pesokg = "0.0" + pesokg1.substr(3);
        } else if (pesokg1.startsWith("00")) {
          pesokg = "0." + pesokg1.substr(2);
        } else if (pesokg1.startsWith("0")) {
          pesokg =
            pesokg1.substr(1, 1) + "." + pesokg1.substr(2, pesokg1.length);
        } else if (!pesokg1.startsWith("0")) {
          pesokg =
            pesokg1.substr(0, 2) + "." + pesokg1.substr(2, pesokg1.length);
        }
        scal_qty = pesokg;
      }
      return scal_qty;
    },
    get_search(first_search) {
      let search_term = "";
      if (
        first_search &&
        first_search.startsWith(this.pos_profile.posa_scale_barcode_start)
      ) {
        search_term = first_search.substr(0, 7);
      } else {
        search_term = first_search;
      }
      return search_term;
    },
    esc_event() {
      this.search = null;
      this.first_search = null;
      this.search_backup = null;
      this.qty = 1;
      this.$refs.debounce_search.focus();
    },
    update_items_details(items) {
      const vm = this;
      if (!items || !items.length) return;

      // Cancel previous request
      if (vm.currentRequest) {
        vm.abortController.abort();
        vm.currentRequest = null;
      }

      vm.abortController = new AbortController();
      
      vm.currentRequest = frappe.call({
        method: "posawesome.posawesome.api.posapp.get_items_details",
        args: {
          pos_profile: vm.pos_profile,
          items_data: items,
        },
        freeze: true,
        signal: vm.abortController.signal,
        callback: function(r) {
          if (r.message) {
            let qtyChanged = false;
            
            items.forEach((item) => {
              const updated_item = r.message.find(
                (element) => element.item_code == item.item_code
              );
              if (updated_item) {
                // Save previous quantity for comparison
                const prev_qty = item.actual_qty;
                
                item.actual_qty = updated_item.actual_qty;
                item.serial_no_data = updated_item.serial_no_data;
                item.batch_no_data = updated_item.batch_no_data;
                
                // Properly handle UOMs data
                if (updated_item.item_uoms && updated_item.item_uoms.length > 0) {
                  item.item_uoms = updated_item.item_uoms;
                } else if (!item.item_uoms || !item.item_uoms.length) {
                  // If no UOMs found, at least add the stock UOM
                  item.item_uoms = [{ uom: item.stock_uom, conversion_factor: 1.0 }];
                }
                
                item.has_batch_no = updated_item.has_batch_no;
                item.has_serial_no = updated_item.has_serial_no;
                
                // Log and track significant quantity changes
                if (prev_qty > 0 && item.actual_qty === 0) {
                  console.log(`Item ${item.item_code} quantity changed from ${prev_qty} to 0`);
                  qtyChanged = true;
                }
              }
            });
            
            // Force update if any item's quantity changed significantly
            if (qtyChanged) {
              vm.$forceUpdate();
            }
          }
        },
        error: function(err) {
          if (err.name !== 'AbortError') {
            console.error("Error fetching item details:", err);
            setTimeout(() => {
              vm.update_items_details(items);
            }, 1000);
          }
        }
      });
      
      // Cleanup on component destroy
      this.cleanupBeforeDestroy = () => {
        if (vm.abortController) {
          vm.abortController.abort();
        }
      };
    },
    update_cur_items_details() {
      if (this.filtered_items && this.filtered_items.length > 0) {
        this.update_items_details(this.filtered_items);
      }
    },
    scan_barcoud() {
      const vm = this;
      try {
        // Check if scanner is already attached to document
        if (document._scannerAttached) {
          return;
        }
        
        onScan.attachTo(document, {
          suffixKeyCodes: [],
          keyCodeMapper: function (oEvent) {
            oEvent.stopImmediatePropagation();
            return onScan.decodeKeyEvent(oEvent);
          },
          onScan: function (sCode) {
            setTimeout(() => {
              vm.trigger_onscan(sCode);
            }, 300);
          },
        });
        
        // Mark document as having scanner attached
        document._scannerAttached = true;
      } catch (error) {
        console.warn('Scanner initialization error:', error.message);
      }
    },
    trigger_onscan(sCode) {
      if (this.filtered_items.length == 0) {
        this.eventBus.emit("show_message", {
          title: `No Item has this barcode "${sCode}"`,
          color: "error",
        });
        frappe.utils.play_sound("error");
      } else {
        this.enter_event();
      }
    },
    generateWordCombinations(inputString) {
      const words = inputString.split(" ");
      const wordCount = words.length;
      const combinations = [];

      // Helper function to generate all permutations
      function permute(arr, m = []) {
        if (arr.length === 0) {
          combinations.push(m.join(" "));
        } else {
          for (let i = 0; i < arr.length; i++) {
            const current = arr.slice();
            const next = current.splice(i, 1);
            permute(current.slice(), m.concat(next));
          }
        }
      }

      permute(words);

      return combinations;
    },
    clearSearch() {
      this.search_backup = this.first_search;
      this.first_search = "";
      this.search = "";
      // No need to call get_items() again
    },
    
    restoreSearch() {
      if (this.first_search === "") {
        this.first_search = this.search_backup;
        this.search = this.search_backup;
        // No need to reload items when focus is lost
      }
    },
    handleItemSearchFocus() {
      this.first_search = "";
      this.search = "";
      // Optionally, you might want to also clear search_backup if the behaviour should be a full reset on focus
      // this.search_backup = ""; 
    },
    getConvertedRate(item) {
      if (!item.rate) return 0;
      if (!this.exchange_rate) return item.rate;
      
      // If exchange rate is 300 PKR = 1 USD
      // To convert PKR to USD: divide by exchange rate
      // Example: 3000 PKR / 300 = 10 USD
      const convertedRate = item.rate / this.exchange_rate;
      return this.flt(convertedRate, 4);
    },
    currencySymbol(currency) {
      return get_currency_symbol(currency);
    },
    format_currency(value, currency, precision) {
      if (!value) return '0';
      
      // Convert to string for checking decimal points
      let valueStr = value.toString();
      
      // If value has decimal points, show 4 decimal places
      if (valueStr.includes('.')) {
        return flt(value, 4).toString();
      }
      
      // For whole numbers, return as is
      return valueStr;
    },
    format_number(value, precision) {
      if (!value) return '0';
      
      // Convert to string for checking decimal points
      let valueStr = value.toString();
      
      // If value has decimal points, show 4 decimal places
      if (valueStr.includes('.')) {
        return flt(value, 4).toString();
      }
      
      // For whole numbers, return as is
      return valueStr;
    },
    hasDecimalPrecision(value) {
      // Check if the value has any decimal precision when multiplied by exchange rate
      if (this.exchange_rate && this.exchange_rate !== 1) {
        let convertedValue = value * this.exchange_rate;
        return !Number.isInteger(convertedValue);
      }
      return !Number.isInteger(value);
    },
  },

  computed: {
    filtered_items() {
      this.search = this.get_search(this.first_search);
      if (!this.pos_profile.pose_use_limit_search) {
        let filtred_list = [];
        let filtred_group_list = [];
        if (this.item_group != "ALL") {
          filtred_group_list = this.items.filter((item) =>
            item.item_group
              .toLowerCase()
              .includes(this.item_group.toLowerCase())
          );
        } else {
          filtred_group_list = this.items;
        }
        if (!this.search || this.search.length < 3) {
          let filtered = [];
          if (
            this.pos_profile.posa_show_template_items &&
            this.pos_profile.posa_hide_variants_items
          ) {
            filtered = filtred_group_list
              .filter((item) => !item.variant_of)
              .slice(0, 50);
          } else {
            filtered = filtred_group_list.slice(0, 50);
          }
          
          // Ensure quantities are defined
          filtered.forEach(item => {
            if (item.actual_qty === undefined) {
              item.actual_qty = 0;
            }
          });
          
          return filtered;
        } else if (this.search) {
          filtred_list = filtred_group_list.filter((item) => {
            let found = false;
            for (let element of item.item_barcode) {
              if (element.barcode == this.search) {
                found = true;
                break;
              }
            }
            return found;
          });
          if (filtred_list.length == 0) {
            filtred_list = filtred_group_list.filter((item) =>
              item.item_code.toLowerCase().includes(this.search.toLowerCase())
            );
            if (filtred_list.length == 0) {
              const search_combinations = this.generateWordCombinations(
                this.search
              );
              filtred_list = filtred_group_list.filter((item) => {
                let found = false;
                for (let element of search_combinations) {
                  element = element.toLowerCase().trim();
                  let element_regex = new RegExp(
                    `.*${element.split("").join(".*")}.*`
                  );
                  if (element_regex.test(item.item_name.toLowerCase())) {
                    found = true;
                    break;
                  }
                }
                return found;
              });
            }
            if (
              filtred_list.length == 0 &&
              this.pos_profile.posa_search_serial_no
            ) {
              filtred_list = filtred_group_list.filter((item) => {
                let found = false;
                for (let element of item.serial_no_data) {
                  if (element.serial_no == this.search) {
                    found = true;
                    this.flags.serial_no = null;
                    this.flags.serial_no = this.search;
                    break;
                  }
                }
                return found;
              });
            }
            if (
              filtred_list.length == 0 &&
              this.pos_profile.posa_search_batch_no
            ) {
              filtred_list = filtred_group_list.filter((item) => {
                let found = false;
                for (let element of item.batch_no_data) {
                  if (element.batch_no == this.search) {
                    found = true;
                    this.flags.batch_no = null;
                    this.flags.batch_no = this.search;
                    break;
                  }
                }
                return found;
              });
            }
          }
        }
        
        let final_filtered_list = [];
        if (
          this.pos_profile.posa_show_template_items &&
          this.pos_profile.posa_hide_variants_items
        ) {
          final_filtered_list = filtred_list.filter((item) => !item.variant_of).slice(0, 50);
        } else {
          final_filtered_list = filtred_list.slice(0, 50);
        }
        
        // Ensure quantities are defined for each item
        final_filtered_list.forEach(item => {
          if (item.actual_qty === undefined) {
            item.actual_qty = 0;
          }
        });
        
        // Force request quantity update for filtered items
        if (final_filtered_list.length > 0) {
          setTimeout(() => {
            this.update_items_details(final_filtered_list);
          }, 100);
        }
        
        return final_filtered_list;
      } else {
        const items_list = this.items.slice(0, 50);
        
        // Ensure quantities are defined
        items_list.forEach(item => {
          if (item.actual_qty === undefined) {
            item.actual_qty = 0;
          }
        });
        
        return items_list;
      }
    },
    debounce_search: {
      get() {
        return this.first_search;
      },
      set: _.debounce(function (newValue) {
        this.first_search = newValue;
      }, 200),
    },
  },

  created: function () {
    this.$nextTick(function () { });
    this.eventBus.on("register_pos_profile", (data) => {
      this.pos_profile = data.pos_profile;
      this.get_items();
      this.get_items_groups();
      this.items_view = this.pos_profile.posa_default_card_view
        ? "card"
        : "list";
    });
    this.eventBus.on("update_cur_items_details", () => {
      this.update_cur_items_details();
    });
    this.eventBus.on("update_offers_counters", (data) => {
      this.offersCount = data.offersCount;
      this.appliedOffersCount = data.appliedOffersCount;
    });
    this.eventBus.on("update_coupons_counters", (data) => {
      this.couponsCount = data.couponsCount;
      this.appliedCouponsCount = data.appliedCouponsCount;
    });
    this.eventBus.on("update_customer_price_list", (data) => {
      this.customer_price_list = data;
    });
    this.eventBus.on("update_customer", (data) => {
      this.customer = data;
    });
    
    // Setup auto-refresh for item quantities
    this.refresh_interval = setInterval(() => {
      if (this.filtered_items && this.filtered_items.length > 0) {
        this.update_cur_items_details();
      }
    }, 30000); // Refresh every 30 seconds

    // Add new event listener for currency changes
    this.eventBus.on("update_currency", (data) => {
      this.selected_currency = data.currency;
      this.exchange_rate = data.exchange_rate;
    });
  },

  mounted() {
    this.scan_barcoud();
  },
  
  beforeUnmount() {
    // Clear interval when component is destroyed
    if (this.refresh_interval) {
      clearInterval(this.refresh_interval);
    }
    
    // Call cleanup function for abort controller
    if (this.cleanupBeforeDestroy) {
      this.cleanupBeforeDestroy();
    }
    
    // Detach scanner if it was attached
    if (document._scannerAttached) {
      try {
        onScan.detachFrom(document);
        document._scannerAttached = false;
      } catch (error) {
        console.warn('Scanner detach error:', error.message);
      }
    }

    this.eventBus.off("update_currency");
  },
};
</script>

<style scoped>
.text-success {
  color: #4CAF50 !important;
}

.sleek-data-table {
  border-radius: 12px !important; /* Match Customer.vue style */
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05) !important; /* Match Customer.vue style */
  background-color: #fff !important; /* Match Customer.vue style */
  overflow: hidden !important; /* Ensures border-radius applies correctly */
}

.sleek-data-table:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08) !important; /* Match Customer.vue style */
}
</style>
