import type { TicketAnalytics } from "@/components/ticket-agent/analytics/types";
import { __ } from "@/translation";
import type {
  DocumentResource,
  RecentSimilarTicket,
  Resource,
  TicketActivities,
  TicketAssignee,
  TicketContact,
} from "@/types";
import type { HDTicket } from "@/types/doctypes";
import { router } from "@/router";
import { createDocumentResource, createResource, toast } from "frappe-ui";
import { reactive } from "vue";

interface MapValue {
  ticket: DocumentResource<HDTicket>;
  assignees: Resource<TicketAssignee[]>;
  contact: Resource<TicketContact>;
  recentSimilarTickets: Resource<RecentSimilarTicket>;
  activities: Resource<TicketActivities>;
  analytics: Resource<TicketAnalytics>;
}

const ticketMap: Record<string, MapValue> = reactive({});

export const useTicket = (ticketId: string | number): MapValue => {
  if (!ticketMap[ticketId]) {
    ticketMap[ticketId] = {
      ticket: createDocumentResource<HDTicket>({
        doctype: "HD Ticket",
        name: ticketId,
        whitelistedMethods: {
          markSeen: "mark_seen",
        },
        setValue: {
          onSuccess: (data: HDTicket) => {
            toast.success(__("Ticket updated successfully."));
            leaveTicketIfAccessLost(ticketId, data);
          },
          onError: (error) => {
            const msg = error.exc_type
              ? (error.messages || error.message || []).join(", ")
              : error.message;
            toast.error(msg);
          },
        },
      }),
      assignees: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_assignees",
        params: { ticket: ticketId },
        auto: true,
      }),
      contact: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_contact",
        params: { ticket: ticketId },
        auto: true,
      }),
      recentSimilarTickets: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_recent_similar_tickets",
        params: { ticket: ticketId },
        auto: true,
      }),
      activities: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_activities",
        params: { ticket: ticketId },
        auto: true,
      }),
      // fetched by the analytics tab, not on ticket open
      analytics: createResource({
        url: "helpdesk.api.ticket_analytics.get_ticket_analytics",
        params: { ticket: ticketId },
        cache: ["Ticket", ticketId, "analytics"],
      }),
    };
  }

  return ticketMap[ticketId];
};

// dimensy: moving a ticket to another team (or to a type of another team) can take it out of the agent's reach. The page
// keeps showing the old data and every further change would fail with "no permission", so say where the ticket went and
// go back to the list. The creator keeps access to the ticket and stays on the page.
function leaveTicketIfAccessLost(ticketId: string | number, saved: HDTicket) {
  createResource({
    url: "frappe.client.has_permission",
    params: { doctype: "HD Ticket", docname: ticketId, perm_type: "read" },
    auto: true,
    onSuccess: (res: { has_permission?: boolean }) => {
      if (res?.has_permission) return;
      toast.info(
        saved?.agent_group
          ? __("Ticket moved to team {0}", [saved.agent_group])
          : __("Ticket moved to another team")
      );
      router.push({ name: "TicketsAgent" });
    },
  });
}

export function reloadTicket(ticketId: string) {
  const ticketData = ticketMap[ticketId];
  if (!ticketData) return;
  ticketData.ticket.reload();
  ticketData.assignees.reload();
  ticketData.activities.reload();
}

// Refresh a ticket that may have gone stale
export function revalidateTicket(ticketId: string | number) {
  const ticketData = ticketMap[ticketId];
  if (ticketData?.ticket.get.fetched && !ticketData.ticket.get.loading) {
    reloadTicket(ticketId as string);
  }
}
