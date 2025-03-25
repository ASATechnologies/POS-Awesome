<template>
  <div class="custom-date-picker">
    <div class="date-input" @click="showPicker = true">
      <v-text-field
        v-model="formattedDate"
        :label="frappe._('Posting Date')"
        readonly
        variant="outlined"
        density="compact"
        bg-color="white"
        clearable
        color="primary"
        hide-details
        append-inner-icon="mdi-calendar"
      ></v-text-field>
    </div>

    <v-dialog v-model="showPicker" max-width="360">
      <v-card>
        <v-card-title class="calendar-header">
          <v-btn icon @click="previousMonth">
            <v-icon>mdi-chevron-left</v-icon>
          </v-btn>
          <span>{{ currentMonthYear }}</span>
          <v-btn icon @click="nextMonth">
            <v-icon>mdi-chevron-right</v-icon>
          </v-btn>
        </v-card-title>

        <v-card-text>
          <div class="calendar">
            <div class="weekdays">
              <div v-for="day in weekDays" :key="day">{{ day }}</div>
            </div>
            <div class="days">
              <div
                v-for="day in calendarDays"
                :key="day.date"
                class="day"
                :class="{
                  'selected': isSelected(day.date),
                  'today': isToday(day.date),
                  'disabled': !isInRange(day.date),
                  'other-month': day.isOtherMonth
                }"
                @click="selectAndConfirmDate(day.date)"
              >
                {{ day.dayOfMonth }}
              </div>
            </div>
          </div>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" variant="tonal" @click="clearDate">
            {{ __("Clear") }}
          </v-btn>
          <v-btn color="success" variant="tonal" @click="setTodayDate">
            {{ __("Today") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
export default {
  name: 'PostingDate',
  props: {
    value: {
      type: String,
      default: () => frappe.datetime.nowdate()
    },
    minDate: {
      type: String,
      default: null
    },
    maxDate: {
      type: String,
      default: null
    }
  },
  data() {
    return {
      showPicker: false,
      currentDate: new Date(),
      selectedDate: frappe.datetime.nowdate(),
      weekDays: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
      tempSelectedDate: frappe.datetime.nowdate()
    }
  },
  computed: {
    currentMonthYear() {
      const month = this.currentDate.toLocaleString('default', { month: 'long' });
      const year = this.currentDate.getFullYear();
      return `${month} ${year}`;
    },
    formattedDate() {
      if (!this.selectedDate) return ''
      return frappe.datetime.str_to_user(this.selectedDate)
    },
    calendarDays() {
      const days = []
      const firstDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1)
      const lastDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 0)
      
      // Add days from previous month
      const firstDayWeekday = firstDay.getDay()
      for (let i = firstDayWeekday; i > 0; i--) {
        const date = new Date(firstDay)
        date.setDate(date.getDate() - i)
        days.push({
          date: this.formatDate(date),
          dayOfMonth: date.getDate(),
          isOtherMonth: true
        })
      }

      // Add days of current month
      for (let i = 1; i <= lastDay.getDate(); i++) {
        const date = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), i)
        days.push({
          date: this.formatDate(date),
          dayOfMonth: i,
          isOtherMonth: false
        })
      }

      // Add days from next month
      const remainingDays = 42 - days.length // 6 rows * 7 days = 42
      for (let i = 1; i <= remainingDays; i++) {
        const date = new Date(lastDay)
        date.setDate(date.getDate() + i)
        days.push({
          date: this.formatDate(date),
          dayOfMonth: date.getDate(),
          isOtherMonth: true
        })
      }

      return days
    }
  },
  methods: {
    previousMonth() {
      this.currentDate = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() - 1)
    },
    nextMonth() {
      this.currentDate = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1)
    },
    selectAndConfirmDate(date) {
      if (this.isInRange(date)) {
        this.selectedDate = date;
        this.tempSelectedDate = date;
        this.$emit('input', date);
        this.$emit('update:modelValue', date);
        this.showPicker = false;
      }
    },
    clearDate() {
      this.selectedDate = null;
      this.tempSelectedDate = null;
      this.$emit('input', null);
      this.$emit('update:modelValue', null);
    },
    isSelected(date) {
      return this.tempSelectedDate === date
    },
    isToday(date) {
      return date === frappe.datetime.nowdate()
    },
    isInRange(date) {
      if (!date) return false
      
      const currentDate = frappe.datetime.str_to_obj(date)
      let isValid = true

      if (this.minDate) {
        const minDate = frappe.datetime.str_to_obj(this.minDate)
        isValid = isValid && currentDate >= minDate
      }

      if (this.maxDate) {
        const maxDate = frappe.datetime.str_to_obj(this.maxDate)
        isValid = isValid && currentDate <= maxDate
      }

      return isValid
    },
    formatDate(date) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    },
    setTodayDate() {
      const today = frappe.datetime.nowdate();
      this.selectedDate = today;
      this.tempSelectedDate = today;
      this.currentDate = frappe.datetime.str_to_obj(today);
      this.$emit('input', today);
      this.$emit('update:modelValue', today);
      this.showPicker = false;
    }
  },
  created() {
    // Set default date to today if no value is provided
    const defaultDate = this.value || frappe.datetime.nowdate();
    this.selectedDate = defaultDate;
    this.tempSelectedDate = defaultDate;
    this.currentDate = frappe.datetime.str_to_obj(defaultDate);
    
    // Emit the default value
    this.$emit('input', defaultDate);
    this.$emit('update:modelValue', defaultDate);
  },
  watch: {
    value: {
      handler(newVal) {
        this.selectedDate = newVal
        this.tempSelectedDate = newVal
        if (newVal) {
          this.currentDate = frappe.datetime.str_to_obj(newVal)
        }
      },
      immediate: true
    }
  }
}
</script>

<style scoped>
.custom-date-picker {
  width: 100%;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--v-primary-base);
  color: rgb(0, 0, 0);
}

.calendar-header span {
  font-size: 16px;
  font-weight: 500;
  text-transform: capitalize;
  flex: 1;
  text-align: center;
}

.calendar {
  padding: 16px;
  background: white;
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-weight: 600;
  margin-bottom: 8px;
  color: rgba(0, 0, 0, 0.87);
}

.days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.day {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  transition: all 0.3s;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.87);
}

.day:hover:not(.disabled) {
  background-color: rgba(var(--v-theme-primary), 0.1);
}

.selected {
  background-color: var(--v-primary-base) !important;
  color: rgb(17, 0, 255) !important;
  font-weight: 600;
}

.today {
  border: 2px solid var(--v-primary-base);
  font-weight: 600;
}

.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  color: rgba(0, 0, 0, 0.38);
}

.other-month {
  opacity: 0.5;
  color: rgba(0, 0, 0, 0.38);
}

.v-dialog {
  border-radius: 8px;
  overflow: hidden;
}

.v-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.v-card-actions {
  padding: 16px;
  border-top: 1px solid rgba(0,0,0,0.12);
  display: flex;
  gap: 8px;
}

.v-btn {
  text-transform: none;
  font-weight: 500;
  min-width: 90px !important;
}
</style> 
