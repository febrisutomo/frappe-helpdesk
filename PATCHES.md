# Patch Dimensy pada Frappe Helpdesk

Basis: Helpdesk v1.30.1 (cabang `dimensy/v1.30`). Tiap patch satu commit berawalan `dimensy:`. Rencana: `docs/patch-plan.md` di repo proyek Dimensy.

| # | Commit | Berkas | Tujuan |
|---|---|---|---|
| P1 | `dimensy: sembunyikan data internal tiket dari non-agen` | `helpdesk/utils.py`, `helpdesk/helpdesk/doctype/hd_ticket/api.py`, `test_hd_ticket.py` | `get_one` membuang `INTERNAL_TICKET_FIELDS` (prioritas, team, SLA, `_assign`, `_comments`, dan sebagainya) untuk non-agen; `get_communications` mengganti pengirim balasan agen dengan nama tim (`helpdesk_customer_agent_name` di site config, bawaan "Support Team") dan membuang `bcc`. Penentuan berdasarkan peran di server, bukan parameter klien. Perilaku agen tidak berubah. Uji: `test_get_one_hides_internal_data_from_non_agents`. |
| P2 | `dimensy: daftar tiket customer tanpa kolom internal` | `helpdesk/api/doc.py`, `test_hd_ticket.py` | `get_list_data`, `sort_options`, dan `get_quick_filters` memaksa mode portal untuk non-agen; kolom, baris, dan data yang diminta klien disaring dengan `INTERNAL_TICKET_FIELDS`; daftar field portal tidak lagi memuat `priority`, `response_by`, `resolution_by`. Uji: `test_get_list_data_hides_internal_columns_from_non_agents`. |
| P3 | `dimensy: sidebar tiket customer tanpa Team, Priority, dan SLA` | `desk/src/components/ticket/TicketCustomerSidebar.vue` | Hapus baris Team dan Priority serta blok SLA (First Response, Resolution) dari sidebar portal customer; impor dan perhitungan SLA yang tidak lagi dipakai ikut dibuang. Uji: Playwright (customer, desktop dan mobile). |
