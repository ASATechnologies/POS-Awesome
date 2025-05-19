<template>
  <!-- Main navigation container -->
  <nav>
    <!-- Top App Bar: application header with nav toggle, logo, title, and actions -->
    <v-app-bar app flat height="56" color="white" class="border-bottom">
      <!-- Nav icon: toggles side drawer -->
      <v-app-bar-nav-icon ref="navIcon" @click="handleNavClick" class="text-secondary" />

      <!-- Logo: POS Awesome brand image -->
      <v-img src="/assets/posawesome/js/posapp/components/pos/pos.png" alt="POS Awesome" max-width="32" class="mx-3" />

      <!-- Title: clickable to navigate to desk view -->
      <v-toolbar-title @click="goDesk" class="text-h6 font-weight-bold text-primary" style="cursor: pointer;">
        <span class="font-weight-light">POS</span><span>Awesome</span>
      </v-toolbar-title>

      <v-spacer />

      <!-- Profile Button: displays current POS profile name -->
      <v-btn style="cursor: unset; text-transform: none;" variant="text" color="primary">
        {{ posProfile.name }}
      </v-btn>

      <!-- User Menu: dropdown for shift, print, logout, and about actions -->
      <v-menu offset-y offset-x :min-width="200">
        <template #activator="{ props }">
          <v-btn v-bind="props" color="primary" theme="dark" variant="text" class="user-menu-btn">
            {{ __('Menu') }}
            <v-icon right>mdi-menu-down</v-icon>
          </v-btn>
        </template>

        <v-card class="user-menu-card" tile>
          <v-list dense class="user-menu-list">
            <v-list-item v-if="!posProfile.posa_hide_closing_shift" @click="openCloseShift" class="user-menu-item">
              <v-list-item-icon><v-icon>mdi-content-save-move-outline</v-icon></v-list-item-icon>
              <v-list-item-title>{{ __('Close Shift') }}</v-list-item-title>
            </v-list-item>

            <v-list-item v-if="posProfile.posa_allow_print_last_invoice && lastInvoiceId" @click="printLastInvoice"
              class="user-menu-item">
              <v-list-item-icon><v-icon>mdi-printer</v-icon></v-list-item-icon>
              <v-list-item-title>{{ __('Print Last Invoice') }}</v-list-item-title>
            </v-list-item>

            <v-divider class="my-2" />

            <v-list-item @click="logOut" class="user-menu-item">
              <v-list-item-icon><v-icon>mdi-logout</v-icon></v-list-item-icon>
              <v-list-item-title>{{ __('Logout') }}</v-list-item-title>
            </v-list-item>

            <v-list-item @click="goAbout" class="user-menu-item">
              <v-list-item-icon><v-icon>mdi-information-outline</v-icon></v-list-item-icon>
              <v-list-item-title>{{ __('About') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>
      </v-menu>
    </v-app-bar>

    <!-- Side Navigation Drawer -->
    <v-navigation-drawer app v-model="drawer" :mini-variant="mini" expand-on-hover width="220" class="drawer-custom"
      @mouseleave="handleMouseLeave">
      <!-- Expanded Header -->
      <div v-if="!mini" class="drawer-header">
        <v-avatar size="40"><v-img :src="companyImg" alt="Company logo" /></v-avatar>
        <span class="drawer-company">{{ company }}</span>
        <v-btn icon @click.stop="mini = true"><v-icon>mdi-chevron-left</v-icon></v-btn>
      </div>
      <!-- Mini Header -->
      <div v-else class="drawer-header-mini">
        <v-avatar size="40"><v-img :src="companyImg" alt="Company logo" /></v-avatar>
      </div>

      <v-divider />

      <!-- Navigation Items -->
      <v-list dense nav>
        <v-list-item-group v-model="item" active-class="active-item">
          <v-list-item v-for="i in items" :key="i.text" @click="changePage(i.text)" class="drawer-item">
            <v-list-item-icon><v-icon class="drawer-icon">{{ i.icon }}</v-icon></v-list-item-icon>
            <v-list-item-content v-if="!mini">
              <v-list-item-title class="drawer-item-title">{{ i.text }}</v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list-item-group>
      </v-list>
    </v-navigation-drawer>

    <!-- Snackbar -->
    <v-snackbar v-model="snack" :timeout="5000" :color="snackColor" location="top right">
      {{ snackText }}
    </v-snackbar>

    <!-- Freeze Dialog -->
    <v-dialog v-model="freeze" persistent max-width="290">
      <v-card>
        <v-card-title class="text-h5">{{ freezeTitle }}</v-card-title>
        <v-card-text>{{ freezeMsg }}</v-card-text>
      </v-card>
    </v-dialog>
  </nav>
</template>

<script>
import { eventBus } from '@/eventBus';

export default {
  name: 'NavBar',
  data() {
    return {
      drawer: false,
      mini: true,
      item: 0,
      items: [{ text: 'POS', icon: 'mdi-network-pos' }],
      company: 'POS Awesome',
      companyImg: '/assets/erpnext/images/erpnext-logo.svg',
      posProfile: {},
      lastInvoiceId: null,
      snack: false,
      snackColor: '',
      snackText: '',
      freeze: false,
      freezeTitle: '',
      freezeMsg: ''
    };
  },
  created() {
    const bootCompany = frappe?.boot?.user_info?.company;
    this.company = bootCompany || this.company;
    console.log('Fetched company:', this.company);

    if (this.company !== 'POS Awesome') {
      frappe.call({
        method: 'frappe.client.get',
        args: { doctype: 'Company', name: this.company },
        callback: r => {
          if (r.message?.company_logo) {
            this.companyImg = r.message.company_logo;
          }
        },
        error: err => console.warn('Company lookup failed', err)
      });
    }

    this.$nextTick(() => {
      eventBus.on('show_message', this.showMessage);
      eventBus.on('set_company', data => {
        this.company = data.name || this.company;
        this.companyImg = data.company_logo || this.companyImg;
      });
      eventBus.on('register_pos_profile', data => {
        this.posProfile = data.pos_profile;
        const paymentsItem = { text: 'Payments', icon: 'mdi-cash-register' };
        if (this.posProfile.posa_use_pos_awesome_payments &&
          !this.items.some(i => i.text === 'Payments')) {
          this.items.push(paymentsItem);
        }
      });
      eventBus.on('set_last_invoice', data => {
        this.lastInvoiceId = data;
      });
      eventBus.on('freeze', data => {
        this.freeze = true;
        this.freezeTitle = data.title;
        this.freezeMsg = data.msg;
      });
      eventBus.on('unfreeze', () => {
        this.freeze = false;
        this.freezeTitle = '';
        this.freezeMsg = '';
      });
    });
  },
  methods: {
    handleNavClick() {
      this.drawer = true;
      this.mini = false;
    },
    handleMouseLeave() {
      if (!this.drawer) return;
      clearTimeout(this._closeTimeout);
      this._closeTimeout = setTimeout(() => {
        this.drawer = false;
        this.mini = true;
      }, 250);
    },
    changePage(key) {
      this.$emit('changePage', key);
    },
    goDesk() {
      frappe.set_route('/');
      location.reload();
    },
    openCloseShift() {
      this.eventBus.emit('open_closing_dialog');
    },
    printLastInvoice() {
      if (!this.lastInvoiceId) return;
      const pf = this.posProfile.print_format_for_online || this.posProfile.print_format;
      const noLetterHead = this.posProfile.letter_head || 0;
      const url = `${frappe.urllib.get_base_url()}/printview?doctype=Sales%20Invoice&name=${this.lastInvoiceId}` +
        `&trigger_print=1&format=${pf}&no_letterhead=${noLetterHead}`;
      const win = window.open(url, '_blank');
      win.addEventListener('load', () => win.print(), { once: true });
    },
    goAbout() {
      frappe.call({
        method: 'posawesome.posawesome.api.posapp.get_app_info',
        callback: r => {
          if (Array.isArray(r.message.apps)) {
            let html = `
              <table style="width:100%; border-collapse:collapse; text-align:left;">
                <thead>
                  <tr><th style="padding:8px;">${__('Application')}</th>
                      <th style="padding:8px;">${__('Version')}</th></tr>
                </thead><tbody>
            `;
            r.message.apps.forEach(app => {
              html += `
                <tr>
                  <td style="padding:8px;"><strong>${app.app_name}</strong></td>
                  <td style="padding:8px;">${app.installed_version}</td>
                </tr>
              `;
            });
            html += `</tbody></table>`;

            frappe.msgprint({
              title: __('Installed Applications'),
              indicator: 'blue',
              message: html
            });
          }
        },
        error: () => frappe.msgprint({
          title: __('Error'),
          indicator: 'red',
          message: __('Failed to retrieve app info')
        })
      });
    },
    logOut() {
      frappe.call({
        method: 'logout',
        callback: r => {
          if (!r.exc) {
            frappe.set_route('/app/home');
            location.reload();
          }
        }
      });
    },
    showMessage(data) {
      this.snack = true;
      this.snackColor = data.color;
      this.snackText = data.title;
    }
  }
};
</script>


<style scoped>
.border-bottom {
  border-bottom: 1px solid #e0e0e0;
}

.text-secondary {
  color: rgba(0, 0, 0, 0.6) !important;
}

.drawer-custom {
  background-color: #fafafa;
  transition: all 0.3s ease-out;
}

.drawer-header {
  display: flex;
  align-items: center;
  height: 64px;
  padding: 0 16px;
}

.drawer-header-mini {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 64px;
}

.drawer-company {
  margin-left: 12px;
  flex: 1;
  font-weight: 500;
  font-size: 1rem;
  color: #424242;
}

.drawer-icon {
  font-size: 24px;
  color: #1976d2;
}

.drawer-item-title {
  margin-left: 8px;
  font-weight: 500;
  color: #424242;
}

.v-list-item:hover {
  background-color: rgba(25, 118, 210, 0.1) !important;
}

.active-item {
  background-color: rgba(25, 118, 210, 0.2) !important;
}

.user-menu-btn {
  text-transform: none;
  padding: 4px 12px;
  font-weight: 500;
}

.user-menu-card {
  border-radius: 8px;
  overflow: hidden;
}

.user-menu-list {
  padding-top: 8px;
  padding-bottom: 8px;
}

.user-menu-item {
  padding: 10px 16px;
}

.user-menu-item .v-list-item-icon {
  min-width: 36px;
}

.user-menu-card .v-divider {
  margin: 8px 0;
}
</style>
