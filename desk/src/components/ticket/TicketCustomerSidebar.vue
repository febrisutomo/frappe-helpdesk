<template>
  <div class="flex w-[382px] flex-col border-s gap-4">
    <!-- Ticket ID -->
    <div class="flex items-center justify-between border-b px-5 py-3">
      <span class="cursor-copy text-lg-semibold">Ticket details</span>
    </div>
    <!-- user info and sla info -->
    <div class="flex flex-col gap-4 pt-0 px-5 py-3 border-b">
      <!-- user info -->
      <div class="flex gap-2">
        <Avatar
          size="2xl"
          :image="ticket.data.contact.image"
          :label="ticket.data.contact.name"
        />
        <div class="flex items-center justify-between">
          <Tooltip :text="ticket.data.contact.name">
            <div class="w-[242px] truncate text-3xl-medium">
              {{ ticket.data.contact.name }}
            </div>
          </Tooltip>
          <div
            class="flex gap-1.5"
            v-if="
              !ticket.data.feedback_rating && ticket.data.status !== 'Closed'
            "
          >
            <Tooltip :text="ticket.data.contact.email_id">
              <Button class="h-7 w-7" @click="emit('open')">
                <template #icon>
                  <EmailIcon class="h-4 w-4" />
                </template>
              </Button>
            </Tooltip>
          </div>
        </div>
      </div>

      <!-- Ticket Info -->
      <div
        class="flex items-center text-base leading-5"
        v-for="field in ticketBasicInfo"
      >
        <span class="w-[126px] text-sm text-ink-gray-5">{{ field.label }}</span>
        <span
          class="text-base text-ink-gray-8 flex-1"
          :class="!field.value && 'text-ink-gray-4'"
        >
          {{ field.value || "—" }}
        </span>
      </div>
    </div>
    <!-- feedback component -->
    <TicketFeedback
      v-if="ticket.data.feedback_rating"
      class="border-b text-base text-ink-gray-5"
      :ticket="ticket.data"
    />
    <div class="flex flex-col gap-4 pt-0 px-5 py-3 overflow-y-scroll">
      <div
        class="flex items-center text-base leading-5"
        v-for="field in ticketAdditionalInfo"
        :key="field.fieldname"
      >
        <span class="w-[126px] text-sm text-ink-gray-5">{{ field.label }}</span>
        <span
          class="text-base text-ink-gray-8 flex-1"
          :class="!field.value && 'text-ink-gray-4'"
        >
          <template
            v-if="
              field.value &&
              (field.fieldtype === 'Date' || field.fieldtype === 'Datetime') &&
              dayjs(field.value).isValid()
            "
          >
            {{ dateFormat(field.value, dateTooltipFormat) }}
          </template>
          <template v-else>
            {{ field.value || "—" }}
          </template>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ITicket } from "@/pages/ticket/symbols";
import { Field } from "@/types";
import { dateFormat, dateTooltipFormat } from "@/utils";
import { Avatar, dayjs, Tooltip } from "frappe-ui";
import { computed, inject } from "vue";

const emit = defineEmits(["open"]);

const ticket = inject(ITicket);

const ticketBasicInfo = computed(() => [
  {
    label: "Ticket ID",
    value: ticket.data.name,
  },
  {
    label: "Status",
    value: ticket.data.status,
    bold: true,
  },
]);

const ticketAdditionalInfo = computed(() => {
  const fields = [
    {
      fieldname: "subject",
      label: "Subject",
      value: ticket.data.subject,
    },
  ];
  const custom_fields = ticket.data.template.fields
    .filter(
      (field: Field) =>
        !field.hide_from_customer &&
        ["subject", "team", "priority"].indexOf(field.fieldname) === -1
    )
    .map((field: Field) => {
      const option = {
        label: field.label,
        value: ticket.data[field.fieldname],
      };
      if (field.fieldtype === "Date") {
        option.value = dayjs(option.value).format(
          window.date_format.toUpperCase()
        );
      }
      if (field.fieldtype === "Datetime") {
        // window.time_format
        option.value = dayjs(option.value).format(
          `${window.date_format.toUpperCase()} ${window.time_format}`
        );
      }
      return option;
    });

  return [...fields, ...custom_fields];
});
</script>

<style scoped></style>
