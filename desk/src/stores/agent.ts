import { computed } from "vue";
import { defineStore } from "pinia";
import { createListResource } from "frappe-ui";

export const useAgentStore = defineStore("agent", () => {
  const agents = createListResource({
    doctype: "HD Agent",
    fields: ["name", "agent_name", "user", "user.user_image"],
    filters: { is_active: 1 },
    pageLength: 99999,
  });

  const dropdown = computed(() =>
    agents.data?.map((o) => ({
      label: o.agent_name,
      value: o.name,
      image: o.user_image,
    }))
  );

  // dimensy: teams can be mentioned too (@CS, @ASO ...); the backend notifies every member of the team
  const teams = createListResource({
    doctype: "HD Team",
    fields: ["name"],
    pageLength: 999,
    auto: true,
  });
  const mentionables = computed(() => [
    ...(teams.data ?? []).map((t) => ({
      label: "Team " + t.name,
      value: "team:" + t.name,
    })),
    ...(dropdown.value ?? []),
  ]);

  function searchAgents(query: string) {
    return agents.data.filter((a) =>
      a.user?.toLowerCase().includes(query.toLowerCase())
    );
  }

  return {
    dropdown,
    mentionables,
    teams,
    agents,
    searchAgents,
  };
});
