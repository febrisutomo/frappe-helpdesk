# Patch Dimensy pada Frappe Helpdesk

Basis: Helpdesk v1.30.1 (cabang `dimensy/v1.30`). Tiap patch satu commit berawalan `dimensy:`. Rencana: `docs/rencana-patch.md` di repo proyek Dimensy.

| # | Commit | Berkas | Tujuan |
|---|---|---|---|
| P1 | `dimensy: sembunyikan data internal tiket dari non-agen` | `helpdesk/utils.py`, `helpdesk/helpdesk/doctype/hd_ticket/api.py`, `test_hd_ticket.py` | `get_one` membuang `INTERNAL_TICKET_FIELDS` (prioritas, team, SLA, `_assign`, `_comments`, dan sebagainya) untuk non-agen; `get_communications` mengganti pengirim balasan agen dengan nama tim (`helpdesk_customer_agent_name` di site config, bawaan "Support Team") dan membuang `bcc`. Penentuan berdasarkan peran di server, bukan parameter klien. Perilaku agen tidak berubah. Uji: `test_get_one_hides_internal_data_from_non_agents`. |
