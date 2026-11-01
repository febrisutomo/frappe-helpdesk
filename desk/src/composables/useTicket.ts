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

// dimensy: tickets the agent may be about to lose access to (after moving them to another team). Reloading such a ticket would
// only fail with "no permission" and toast it, so reloads wait until the access check says whether the agent stays.
const departing = new Set<string | number>();
export const markDeparting = (ticketId: string | number) =>
  departing.add(ticketId);
export const unmarkDeparting = (ticketId: string | number) =>
  departing.delete(ticketId);
export const isDeparting = (ticketId: string | number) =>
  departing.has(ticketId);

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
            leaveTicketIfAccessLost(ticketId, data?.agent_group);
          },
          onError: (error) => {
            unmarkDeparting(ticketId);
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
// Resolves true when the agent lost access and was sent back to the list, false when the agent stays (then the ticket is
// reloaded, which the change skipped while the check was pending).
export async function leaveTicketIfAccessLost(
  ticketId: string | number,
  team?: string
): Promise<boolean> {
  markDeparting(ticketId);
  let allowed = true;
  try {
    const res = await createResource({
      url: "frappe.client.has_permission",
      params: { doctype: "HD Ticket", docname: ticketId, perm_type: "read" },
    }).fetch();
    allowed = Boolean(res?.has_permission);
  } catch {
    allowed = true; // cannot tell: stay, the page shows its own errors
  }
  if (allowed) {
    unmarkDeparting(ticketId);
    reloadTicket(String(ticketId));
    return false;
  }
  toast.info(
    team
      ? __("Ticket moved to team {0}", [team])
      : __("You no longer have access to this ticket")
  );
  router.push({ name: "TicketsAgent" });
  setTimeout(() => unmarkDeparting(ticketId), 5000);
  return true;
}

export function reloadTicket(ticketId: string) {
  const ticketData = ticketMap[ticketId];
  if (!ticketData || departing.has(ticketId)) return;
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
