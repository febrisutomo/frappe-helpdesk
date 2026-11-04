import { __ } from "@/translation";
import { createResource } from "frappe-ui";
import { reactive, watch } from "vue";

// dimensy: changes of a ticket that cannot be taken back from the agent's side, or that send mail or move the ticket out of the
// agent's reach, ask for a confirmation before they are saved. Dialogs that already exist (merge, split, bulk reply, publishing
// articles) are not repeated here.

type Doc = Record<string, any>;
type Dialog = (options: Record<string, any>) => void;
type Confirmation = { title: string; message: string; label: string };

async function defaultTeam(ticketType: string): Promise<string> {
  const result = await createResource({
    url: "frappe.client.get_value",
    params: {
      doctype: "HD Ticket Type",
      filters: { name: ticketType },
      fieldname: "custom_team",
    },
  }).fetch();
  return typeof result === "string" ? result : result?.custom_team || "";
}

function moveConfirmation(team: string, incident: boolean): Confirmation {
  const lines = [
    __("The ticket moves to team {0} and its agent is replaced.", [team]),
    __(
      "Unless you created it yourself, you will no longer be able to open it."
    ),
    __("Write a handover note in a comment first."),
  ];
  if (incident) {
    lines.push(
      __("A security incident ticket alerts the Security team.")
    );
  }
  return {
    title: __("Move this ticket to team {0}?", [team]),
    message: lines.join(" "),
    label: __("Move ticket"),
  };
}

export async function confirmationFor(
  doc: Doc,
  fieldname: string,
  value: unknown
): Promise<Confirmation | null> {
  if (fieldname === "agent_group" && value && value !== doc.agent_group) {
    return moveConfirmation(String(value), false);
  }
  if (fieldname === "ticket_type" && value) {
    const team = await defaultTeam(String(value));
    if (team && team !== doc.agent_group) {
      return moveConfirmation(team, String(value).startsWith("INS - "));
    }
    return null;
  }
  if (fieldname === "custom_revocation_validated" && value && !doc[fieldname]) {
    return {
      title: __("Mark this request as validated?"),
      message: __(
        "This cannot be undone. The revocation deadline starts now and the ticket can no longer be set to Replied."
      ),
      label: __("Mark as validated"),
    };
  }
  if (fieldname === "priority" && value === "Urgent" && doc.priority !== "Urgent") {
    return {
      title: __("Raise the priority to Urgent?"),
      message: __(
        "The team and the managers are alerted early by email, and the ticket follows the Urgent SLA."
      ),
      label: __("Set to Urgent"),
    };
  }
  return null;
}

// Resolves true when the change may be saved: nothing to confirm, or the agent confirmed. Closing the dialog resolves false.
export function askConfirmation(
  $dialog: Dialog,
  confirmation: Confirmation
): Promise<boolean> {
  return new Promise((resolve) => {
    let answered = false;
    const options = reactive({
      title: confirmation.title,
      message: confirmation.message,
      actions: [
        {
          label: confirmation.label,
          variant: "solid",
          onClick({ close }: { close: () => void }) {
            answered = true;
            resolve(true);
            close();
          },
        },
      ],
      show: false,
    });
    $dialog(options);
    // the dialog host flips `show` when it is dismissed
    const stop = watch(
      () => options.show,
      (shown, wasShown) => {
        if (wasShown && !shown) {
          if (!answered) resolve(false);
          stop();
        }
      }
    );
  });
}

export async function confirmTicketChange(
  $dialog: Dialog,
  doc: Doc,
  fieldname: string,
  value: unknown
): Promise<boolean> {
  const confirmation = await confirmationFor(doc, fieldname, value);
  return confirmation ? askConfirmation($dialog, confirmation) : true;
}
