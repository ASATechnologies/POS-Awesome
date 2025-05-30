<template>
  <!-- Main navigation container -->
  <nav>
     <!-- Top App Bar: application header with nav toggle, logo, title, and actions -->
    <v-app-bar app flat height="56" color="white" class="border-bottom">
      <v-app-bar-nav-icon ref="navIcon" @click="handleNavClick" class="text-secondary" />

      <v-img src="/assets/posawesome/js/posapp/components/pos/pos.png" alt="POS Awesome" max-width="32" class="mx-3" />

      <v-toolbar-title @click="goDesk" class="text-h6 font-weight-bold text-primary" style="cursor: pointer;">
        <span class="font-weight-light">POS</span><span>Awesome</span>
      </v-toolbar-title>

      <v-spacer />

      <!-- This component visually indicates the current network and server connectivity status.
           It changes color and icon based on whether there's internet, server connection, or if it's connecting. -->
      <v-tooltip bottom>
        <template #activator="{ on, attrs }">
          <v-btn icon v-bind="attrs" v-on="on" :title="statusText" class="mx-2">
            <v-progress-circular v-if="serverConnecting" indeterminate color="blue" size="24"
              width="2"></v-progress-circular>
            <v-icon v-else :color="statusColor" size="24">
              {{ statusIcon }}
            </v-icon>
          </v-btn>
        </template>
        <span>{{ statusText }}</span>
      </v-tooltip>

      <v-btn style="cursor: unset; text-transform: none;" variant="text" color="primary">
        {{ posProfile.name }}
      </v-btn>

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

    <!-- This drawer slides out from the left, providing additional navigation options.
         It can be in a mini-variant (collapsed) or expanded state. -->
    <v-navigation-drawer app v-model="drawer" :mini-variant="mini" expand-on-hover width="220" class="drawer-custom"
      @mouseleave="handleMouseLeave">
      <div v-if="!mini" class="drawer-header">
        <v-avatar size="40"><v-img :src="companyImg" alt="Company logo" /></v-avatar>
        <span class="drawer-company">{{ company }}</span>
        <v-btn icon @click.stop="mini = true"><v-icon>mdi-chevron-left</v-icon></v-btn>
      </div>
      <div v-else class="drawer-header-mini">
        <v-avatar size="40"><v-img :src="companyImg" alt="Company logo" /></v-avatar>
      </div>

      <v-divider />

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

    <v-snackbar v-model="snack" :timeout="5000" :color="snackColor" location="top right">
      {{ snackText }}
    </v-snackbar>

    <v-dialog v-model="freeze" persistent max-width="290">
      <v-card>
        <v-card-title class="text-h5">{{ freezeTitle }}</v-card-title>
        <v-card-text>{{ freezeMsg }}</v-card-text>
      </v-card>
    </v-dialog>
  </nav>
</template>

<script>
// Import the Socket.IO client library for real-time server status monitoring.
// This import is crucial for the server connectivity indicator.
import { io } from 'socket.io-client';

export default {
  name: 'NavBar', // Component name
  data() {
    return {
      drawer: false, // Controls the visibility of the side navigation drawer (true for open, false for closed)
      mini: true, // Controls the mini-variant (collapsed) state of the drawer (true for collapsed, false for expanded)
      item: 0, // Index of the currently selected item in the drawer list, used for active styling
      items: [{ text: 'POS', icon: 'mdi-network-pos' }], // Array of navigation items for the drawer. Each item has text and a Material Design Icon.
      company: 'POS Awesome', // Default company name, used if not fetched from Frappe boot data
      companyImg: '/assets/erpnext/images/erpnext-logo.svg', // Default path to the company logo image
      posProfile: {}, // Object to store the current POS profile data, fetched from the backend
      lastInvoiceId: null, // Stores the ID of the last generated sales invoice, used for re-printing
      snack: false, // Controls the visibility of the snackbar (true for visible, false for hidden)
      snackColor: '', // Color of the snackbar (e.g., 'success', 'error', 'info')
      snackText: '', // Text content displayed within the snackbar
      freeze: false, // Controls the visibility of the freeze dialog (true for visible, false for hidden)
      freezeTitle: '', // Title text for the freeze dialog
      freezeMsg: '', // Message text for the freeze dialog
      // --- SIGNAL INDICATOR STATES ---
      networkOnline: navigator.onLine, // Boolean: Reflects the browser's current network connectivity (true if online, false if offline)
      serverOnline: false,             // Boolean: Reflects the real-time server health via WebSocket (true if connected, false if disconnected)
      serverConnecting: false,         // Boolean: Indicates if the client is currently attempting to establish a connection to the server via WebSocket
      socket: null                     // Instance of the Socket.IO client, used for real-time communication with the server
    };
  },
  computed: {
    /**
     * Determines the color of the status icon based on current network and server connectivity.
     * @returns {string} A Vuetify color string ('blue', 'green', 'orange', 'red').
     */
    statusColor() {
      if (this.serverConnecting) return 'blue'; // Blue when actively trying to connect to the server
      if (this.networkOnline && this.serverOnline) return 'green'; // Green when both internet and server are connected
      if (this.networkOnline && !this.serverOnline) return 'orange'; // Orange when internet is available but server is unreachable
      return 'red'; // Red when there is no internet connection at all
    },
    /**
     * Determines the Material Design Icon to display based on network and server status.
     * @returns {string} A Material Design Icon class string.
     */
    statusIcon() {
      // Note: 'mdi-loading' is conceptually here, but `v-progress-circular` handles the visual loading state.
      if (this.networkOnline && this.serverOnline) return 'mdi-wifi'; // Wi-Fi icon when connected to server
      if (this.networkOnline && !this.serverOnline) return 'mdi-wifi-strength-alert-outline'; // Wi-Fi with alert for server offline
      return 'mdi-wifi-off'; // Wi-Fi off icon when no internet connection
    },
    /**
     * Provides a descriptive text for the tooltip that appears when hovering over the status icon.
     * This text is also used for the `title` attribute of the button.
     * @returns {string} A localized status message.
     */
    statusText() {
      if (this.serverConnecting) return this.__('Connecting to server...'); // Message when connecting
      if (!this.networkOnline) return this.__('No Internet Connection'); // Message when no internet
      return this.serverOnline ? this.__('Connected to Server') : this.__('Server Offline'); // Messages for server status
    }
  },
  created() {
    // --- LOAD COMPANY INFO FROM FRAPPE BOOT ---
    // Attempts to get the company name from Frappe's boot data.
    const bootCompany = frappe?.boot?.user_info?.company;
    this.company = bootCompany || this.company; // Use boot company or default 'POS Awesome'
    console.log('Fetched company:', this.company);

    // If a specific company name is found (not the default), fetch its logo from Frappe.
    if (this.company !== 'POS Awesome') {
      frappe.call({
        method: 'frappe.client.get',
        args: { doctype: 'Company', name: this.company },
        callback: r => {
          if (r.message?.company_logo) this.companyImg = r.message.company_logo;
        },
        error: err => console.warn('Company lookup failed', err)
      });
    }

    // --- EVENT BUS HANDLERS FOR POS INFO/STATE ---
    // Register event listeners on the global event bus. These listeners react to events
    // emitted from other parts of the application to update the NavBar's state.
    this.$nextTick(() => {
      this.eventBus.on('show_message', this.showMessage); // Listens for requests to show a snackbar message
      this.eventBus.on('set_company', data => { // Listens for updates to company details (name, logo)
        this.company = data.name || this.company;
        this.companyImg = data.company_logo || this.companyImg;
      });
      this.eventBus.on('register_pos_profile', data => { // Listens for the POS profile data
        this.posProfile = data.pos_profile;
        const paymentsItem = { text: 'Payments', icon: 'mdi-cash-register' };
        // Conditionally adds a 'Payments' navigation item if allowed by the POS profile and not already present
        if (this.posProfile.posa_use_pos_awesome_payments && !this.items.some(i => i.text === 'Payments')) {
          this.items.push(paymentsItem);
        }
      });
      this.eventBus.on('set_last_invoice', data => { this.lastInvoiceId = data; }); // Listens for the ID of the last processed invoice
      this.eventBus.on('freeze', data => { // Listens for requests to display a freeze dialog (e.g., during long operations)
        this.freeze = true;
        this.freezeTitle = data.title;
        this.freezeMsg = data.msg;
      });
      this.eventBus.on('unfreeze', () => { // Listens for requests to hide the freeze dialog
        this.freeze = false;
        this.freezeTitle = '';
        this.freezeMsg = '';
      });
    });
  },
  mounted() {
    // --- NETWORK ONLINE/OFFLINE EVENTS ---
    // Attach event listeners to the window object to detect changes in the browser's network status.
    window.addEventListener('online', this.handleOnline); // Fires when the browser regains network connectivity
    window.addEventListener('offline', this.handleOffline); // Fires when the browser loses network connectivity

    // --- SOCKET CONNECTION FOR SERVER STATUS ---
    // Initiates the WebSocket connection to monitor server health.
    this.initSocketConnection();
  },
  beforeDestroy() {
    // --- REMOVE NETWORK LISTENERS ---
    // Crucial cleanup: Remove event listeners from the window to prevent memory leaks
    // when the component is destroyed (e.g., navigating away from the page).
    window.removeEventListener('online', this.handleOnline);
    window.removeEventListener('offline', this.handleOffline);
    // --- CLOSE SOCKET ---
    // Disconnect and clean up Socket.IO listeners to ensure proper resource management.
    if (this.socket) {
      this.socket.off('connect'); // Remove 'connect' listener
      this.socket.off('disconnect'); // Remove 'disconnect' listener
      this.socket.off('connect_error'); // Remove 'connect_error' listener
      this.socket.close(); // Close the Socket.IO connection
      this.socket = null; // Clear the socket instance to prevent stale references
    }
  },
  methods: {
    /**
     * Initializes the Socket.IO connection to the backend server.
     * This method sets up the connection parameters and defines event listeners
     * for various connection states (connect, disconnect, error).
     */
    initSocketConnection() {
      this.serverConnecting = true; // Set state to indicate connection attempt is in progress
      this.serverOnline = false; // Assume server is offline until a successful connection is made

      try {
        // Determine the base URL for the socket connection.
        // The port '9000' is a common default for Socket.IO servers, but it MUST be adjusted
        // to the actual port your backend's WebSocket server is listening on.
        const protocol = window.location.protocol; // e.g., 'http:', 'https:'
        const host = window.location.hostname; // e.g., 'localhost', 'yourdomain.com'
        const port = '9000'; // IMPORTANT: Configure this to your actual Socket.IO server port!

        this.socket = io(`${protocol}//${host}:${port}`, {
          path: '/socket.io', // Standard path for Socket.IO connections
          transports: ['websocket', 'polling'], // Preferred transport methods (websocket is faster)
          reconnection: true, // Enable automatic reconnection attempts if connection is lost
          reconnectionAttempts: Infinity, // Attempt to reconnect indefinitely
          reconnectionDelay: 1000, // Initial delay before first reconnection attempt (1 second)
          reconnectionDelayMax: 5000, // Maximum delay between reconnection attempts (5 seconds)
          timeout: 20000 // How long to wait before considering the connection failed (20 seconds)
        });

        // Event listener for a successful connection to the Socket.IO server.
        this.socket.on('connect', () => {
          this.serverOnline = true; // Update server status to online
          this.serverConnecting = false; // Connection attempt is complete
          console.log('Socket.IO: Connected to server');
        });

        // Event listener for disconnection from the Socket.IO server.
        this.socket.on('disconnect', (reason) => {
          this.serverOnline = false; // Update server status to offline
          this.serverConnecting = false; // No longer connecting if disconnected
          console.warn('Socket.IO: Disconnected from server. Reason:', reason);
          // Socket.IO's `reconnection: true` handles automatic reconnection attempts.
        });

        // Event listener for connection errors (e.g., server not found, refused connection).
        this.socket.on('connect_error', (error) => {
          this.serverOnline = false; // Update server status to offline
          this.serverConnecting = false; // No longer connecting if an error occurred
          console.error('Socket.IO: Connection error:', error.message);
        });

      } catch (err) {
        // Catch any errors during the initial Socket.IO client instantiation.
        this.serverOnline = false;
        this.serverConnecting = false;
        console.error('Failed to initialize Socket.IO connection:', err);
      }
    },
    // --- SIGNAL ONLINE/OFFLINE EVENTS ---
    /**
     * Handles the browser's native 'online' event.
     * When the browser regains network connectivity, it updates the `networkOnline` status
     * and attempts to reconnect to the server if not already connected.
     */
    handleOnline() {
      this.networkOnline = true; // Browser is now online
      console.log('Browser is online');
      // If the server is not online and not currently connecting, and a socket instance exists,
      // explicitly try to connect the socket. This helps in re-establishing server connection
      // immediately after internet recovery.
      if (!this.serverOnline && !this.serverConnecting && this.socket) {
        this.socket.connect();
      } else if (!this.socket) {
        // If for some reason the socket instance is null, re-initialize it.
        this.initSocketConnection();
      }
    },
    /**
     * Handles the browser's native 'offline' event.
     * When the browser loses network connectivity, it updates all relevant status flags
     * and disconnects the Socket.IO connection as the server will be unreachable.
     */
    handleOffline() {
      this.networkOnline = false; // Browser is now offline
      this.serverOnline = false; // Server is considered unreachable if there's no internet
      this.serverConnecting = false; // Stop any ongoing connection attempts
      console.log('Browser is offline');
      // Disconnect the socket gracefully if the network goes offline.
      if (this.socket) {
        this.socket.disconnect();
      }
    },
    // --- NAVIGATION AND POS ACTIONS ---
    /**
     * Toggles the visibility and mini-variant state of the side navigation drawer.
     */
    handleNavClick() {
      this.drawer = true; // Open the drawer
      this.mini = false; // Ensure it's in expanded mode
    },
    /**
     * Handles the mouse leaving the navigation drawer area.
     * If the drawer is open, it sets a timeout to collapse it back to mini-variant.
     */
    handleMouseLeave() {
      if (!this.drawer) return; // Do nothing if the drawer is already closed
      clearTimeout(this._closeTimeout); // Clear any previous timeout to prevent conflicts
      this._closeTimeout = setTimeout(() => {
        this.drawer = false; // Close the drawer
        this.mini = true; // Set it to mini-variant
      }, 250); // Delay for 250 milliseconds
    },
    /**
     * Emits a 'changePage' event to the parent component, signaling a request to navigate to a new page.
     * @param {string} key - The identifier for the page to navigate to (e.g., 'POS', 'Payments').
     */
    changePage(key) {
      this.$emit('changePage', key);
    },
    /**
     * Navigates the user back to the main Frappe desk view and reloads the page.
     */
    goDesk() {
      frappe.set_route('/'); // Set Frappe route to home
      location.reload(); // Reload the entire page
    },
    /**
     * Emits an 'open_closing_dialog' event to the event bus, typically to trigger
     * the display of a dialog for closing the POS shift.
     */
    openCloseShift() {
      this.eventBus.emit('open_closing_dialog');
    },
    /**
     * Prints the last generated sales invoice.
     * It constructs a print URL using the invoice ID and POS profile settings,
     * then opens it in a new window and triggers the print command.
     */
    printLastInvoice() {
      if (!this.lastInvoiceId) return; // Exit if no invoice ID is available
      // Determine the print format to use
      const pf = this.posProfile.print_format_for_online || this.posProfile.print_format;
      // Determine if letterhead should be excluded
      const noLetterHead = this.posProfile.letter_head || 0;
      // Construct the full print URL for the Sales Invoice
      const url = `${frappe.urllib.get_base_url()}/printview?doctype=Sales%20Invoice&name=${this.lastInvoiceId}` +
        `&trigger_print=1&format=${pf}&no_letterhead=${noLetterHead}`;
      const win = window.open(url, '_blank'); // Open the URL in a new browser tab/window
      // Add a one-time event listener to the new window to trigger print once it's loaded
      win.addEventListener('load', () => win.print(), { once: true });
    },
    /**
     * Fetches and displays information about all installed applications from the Frappe backend.
     * It presents this information in a formatted table within a Frappe message dialog.
     */
    goAbout() {
      frappe.call({
        method: 'posawesome.posawesome.api.posapp.get_app_info', // API method to call
        callback: r => {
          if (Array.isArray(r.message.apps)) {
            // Build an HTML table string dynamically from the fetched app data
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

            // Display the generated HTML table in a Frappe message print dialog
            frappe.msgprint({
              title: __('Installed Applications'),
              indicator: 'blue', // Blue indicator for informational message
              message: html
            });
          }
        },
        error: () => frappe.msgprint({ // Error callback if API call fails
          title: __('Error'),
          indicator: 'red', // Red indicator for error message
          message: __('Failed to retrieve app info')
        })
      });
    },
    /**
     * Logs out the current user from the Frappe system.
     * Upon successful logout, it redirects the user to the Frappe home page and reloads.
     */
    logOut() {
      frappe.call({
        method: 'logout', // Frappe API method for logout
        callback: r => {
          if (!r.exc) { // If no exception occurred during logout
            frappe.set_route('/app/home'); // Set route to home
            location.reload(); // Reload the page to complete logout process
          }
        }
      });
    },
    /**
     * Displays a snackbar message at the top right of the screen.
     * @param {object} data - An object containing `color` (for snackbar styling) and `title` (the message text).
     */
    showMessage(data) {
      this.snack = true; // Make snackbar visible
      this.snackColor = data.color; // Set snackbar color
      this.snackText = data.title; // Set snackbar text
    },
    /**
     * A dummy translation method. In a real Frappe environment, `frappe.__` or `window.__`
     * would be used for proper internationalization. This is a placeholder for demonstration.
     * @param {string} text - The text string to be translated.
     * @returns {string} The original text (as this is a dummy implementation).
     */
    __(text) {
      // In a real Frappe environment, you would use frappe.__ or window.__
      // For this example, we'll return the text as is.
      return text;
    }
  }
};
</script>

<style scoped>
/* --- App Bar and Drawer Styling --- */
/* Styles related to the main application bar and the side navigation drawer. */

/* Adds a subtle bottom border to the app bar for visual separation. */
.border-bottom {
  border-bottom: 1px solid #e0e0e0;
}

/* Sets a secondary text color, typically a lighter shade of black. */
.text-secondary {
  color: rgba(0, 0, 0, 0.6) !important;
}

/* Custom styling for the navigation drawer, including background and transition effects. */
.drawer-custom {
  background-color: #fafafa;
  transition: all 0.3s ease-out;
}

/* Styling for the header section of the expanded navigation drawer. */
.drawer-header {
  display: flex;
  align-items: center;
  height: 64px;
  padding: 0 16px;
}

/* Styling for the header section of the mini (collapsed) navigation drawer. */
.drawer-header-mini {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 64px;
}

/* Styling for the company name text within the drawer header. */
.drawer-company {
  margin-left: 12px;
  flex: 1;
  font-weight: 500;
  font-size: 1rem;
  color: #424242;
}

/* Styling for icons within the navigation drawer list items. */
.drawer-icon {
  font-size: 24px;
  color: #1976d2;
}

/* Styling for the title text of navigation drawer list items. */
.drawer-item-title {
  margin-left: 8px;
  font-weight: 500;
  color: #424242;
}

/* Hover effect for all list items in the navigation drawer. */
.v-list-item:hover {
  background-color: rgba(25, 118, 210, 0.1) !important;
}

/* Styling for the actively selected list item in the navigation drawer. */
.active-item {
  background-color: rgba(25, 118, 210, 0.2) !important;
}

/* --- User Menu Styling --- */
/* Styles specific to the user actions dropdown menu. */

/* Styling for the main "Menu" button that activates the dropdown. */
.user-menu-btn {
  text-transform: none;
  padding: 4px 12px;
  font-weight: 500;
}

/* Styling for the card that contains the dropdown menu list. */
.user-menu-card {
  border-radius: 8px;
  overflow: hidden;
}

/* Padding for the list within the user menu card. */
.user-menu-list {
  padding-top: 8px;
  padding-bottom: 8px;
}

/* Padding for individual list items within the user menu. */
.user-menu-item {
  padding: 10px 16px;
}

/* Minimum width for icons within user menu list items to ensure alignment. */
.user-menu-item .v-list-item-icon {
  min-width: 36px;
}

/* Margin for dividers within the user menu list. */
.user-menu-card .v-divider {
  margin: 8px 0;
}
</style>
