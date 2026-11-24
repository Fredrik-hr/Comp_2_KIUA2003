"""UI strings for the review UI in bokmål, nynorsk and English.

Only the interface is translated. Extracts, titles and agenda text are always shown as
written in the source.
"""

from __future__ import annotations

LANGS = ("nb", "nn", "en")

UI = {
    "nb": {
        # layout
        "org": "Møtesekretariatet · Innlandet fylkeskommune", "main_nav": "Hovedmeny",
        "meetings": "Møter", "how": "Slik fungerer det", "lang_label": "Språk",
        "test_banner": "Testmiljø – ikke i drift. Briefer deles først etter godkjenning.",
        "crumb": "Brødsmuler",
        # meetings list
        "meetings_lead": "Kjøringer som venter på eller har fått gjennomgang. Nyeste først.",
        "no_runs": "Ingen kjøringer ennå. Last opp en agenda for å starte.",
        "items_n": "saker", "approved_n": "godkjent", "awaiting_n": "venter på gjennomgang",
        "extracts": "utdrag", "attachments_n": "vedlegg", "pages": "sider", "run": "Kjøring",
        "written": "Målform", "brief_in": "brief på", "style": "stil",
        "approved_of": "av {n} saker godkjent",
        "upload_title": "Last opp agenda",
        "upload_lead": "Velg en agendafil eller møteinnkallingen (PDF/Word). Den kontrolleres "
                       "før noe lagres, og du ser hvordan "
                       "den ble lest før du starter kjøringen.",
        "upload_field": "Agenda (.yaml/.yml maks 200 KB, eller møteinnkalling som .pdf/.docx)",
        "upload_button": "Last opp og kontroller",
        "example": "Last ned eksempelagenda (agenda.yaml)",
        "upload_note": "Vedleggene hentes fra lenkene i agendaen. Lukkede saker behandles "
                       "aldri. Du kan også legge filen rett i mappen inbox/.",
        # meeting page
        "share_pdf": "Del som PDF", "export_h": "Brief til møtet (PDF)",
        "export_lead": "Én PDF med alle godkjente saker som du kan dele med deltakerne: "
                       "forside med saksliste og sidetall, en kort orientering per sak og "
                       "alle utdrag som vedlegg.",
        "export_blocked": "Disse sakene må godkjennes eller avvises før du kan lage PDF-en:",
        "export_ready": "Alle behandlede saker er godkjent eller avvist.",
        "meeting_note": "Merknad til hele møtet (valgfritt)",
        "pdf_language": "Språk i PDF-en",
        "confirm_pii": "Jeg har kontrollert at utdragene ikke inneholder personopplysninger.",
        "pii_warning": "Navn i løpende tekst blir ikke oppdaget automatisk. Les gjennom "
                       "utdragene før du deler.",
        "download_pdf": "Last ned PDF", "in_pdf": "I PDF-en",
        "entry": {"approved": "brief", "rejected": "ingen brief", "closed": "lukket sak",
                  "procedural": "formalitet", "scope": "utenfor omfang"},
        "public_url": "Offentlig lenke til møtet (valgfritt)",
        "orientation": "Orientering", "orient_lead": "Det viktigste per sak, kort og ordrett fra "
                       "sakspapirene: hva som skal vedtas, bakgrunn, konsekvenser, vurdering og "
                       "innspill. Se hele briefen for alle utdrag.",
        "not_approved": "Ikke godkjent ennå", "show_full": "Vis hele utdraget",
        "more_in_brief": "{n} til i hele briefen", "open_brief": "Hele briefen",
        "no_extracts_yet": "Ingen utdrag.", "why_h": "Hvorfor dette utdraget?",
        "categories": {"decision": "Hva skal vedtas", "background": "Hva saken gjelder",
                       "consequences": "Konsekvenser", "assessment": "Vurdering",
                       "input": "Innspill", "other": "Annet relevant"},
        "relevance": {"direct": "Direkte relevant", "supporting": "Støttende",
                      "cross_reference": "Kryssreferanse"},
        "start_review": "Start gjennomgang", "summary": "Sammendrag",
        "stat_items": "saker på sakslisten", "stat_awaiting": "venter på gjennomgang",
        "stat_approved": "godkjent", "stat_checked": "utdrag bestod kontroll mot kilden",
        "agenda_file": "Agendafil", "attachment": "Vedlegg", "show_raw": "Vis agendafilen",
        "col1": "Agenda (innlest)", "col2": "Tolkning", "col3": "Brief (resultat)",
        "open": "åpen", "closed": "lukket", "in_scope": "i omfang", "out_scope": "utenfor omfang",
        "recommendation": "Innstilling", "topic": "Tema slik systemet forstod saken",
        "queries": "Søk som ble kjørt", "no_interp": "Ingen tolkning – saken ble ikke søkt i.",
        "review": "Gjennomgå", "raw_title": "Agendafilen slik den ble lest",
        "agenda_missing": "Agendafilen er ikke tilgjengelig lenger.",
        "llm_calls": "LLM-kall", "tokens": "tokens", "seconds": "s",
        "halted": "Stoppet",
        # statuses and types
        "status": {"awaiting_review": "Venter på gjennomgang", "approved": "Godkjent",
                   "rejected": "Avvist", "skipped": "Ikke behandlet", "halted": "Stoppet",
                   "draft_incomplete": "Ufullstendig utkast"},
        "types": {"procedural": "formalitet", "information": "orientering", "case": "sak",
                  "question": "spørsmål"},
        # item page
        "items_in_meeting": "Saker i møtet", "verification": "Kontroll mot kilden",
        "interpretation": "Slik systemet forstod saken", "actions": "Handlinger",
        "language": "Språk i brief", "approve": "Godkjenn brief", "reject": "Avvis",
        "export": "Eksporter", "only_approved": "Kun godkjente briefer kan eksporteres.",
        "approved_msg": "Godkjent.", "note": "Merknad fra møtesekretariatet", "save": "Lagre",
        "extracts_h": "Utdrag", "extracts_sub": "ordrett fra kilden, kan fjernes eller flyttes",
        "kept": "{kept} av {total} utdrag med i briefen", "up": "Flytt opp", "down": "Flytt ned",
        "remove": "Fjern", "restore": "Gjenopprett", "removed": "Fjernet", "page": "side",
        "printed": "trykt", "open_pdf": "åpne PDF på siden", "table_header": "Tabelloverskrift",
        "page_preview": "Forhåndsvisning av side", "audit": "Logg",
        "no_audit": "Ingen handlinger ennå.", "nothing": "Ingen utdrag.",
        "lang_names": {"nb": "bokmål", "nn": "nynorsk", "en": "engelsk"},
        # upload
        "valid_h": "Agendaen er gyldig", "saved_as": "Lagret som", "cancel": "Avbryt",
        "start_run": "Start kjøring", "meeting_read": "Møtet slik det ble lest",
        "body": "Organ", "date": "Dato", "meeting_id": "Møte-ID", "authority": "Myndighet",
        "unique_att": "Vedlegg å hente", "items_h": "Saker",
        "to_process": "behandles", "to_skip": "hoppes over",
        "col_case": "Sak", "col_type": "Type", "col_title": "Tittel",
        "col_att": "Vedlegg", "col_process": "Behandles?", "yes": "Ja",
        "skip": {"closed": "Nei – lukket sak", "procedural": "Nei – formalitet",
                 "scope": "Nei – utenfor omfang"},
        "error_h": "Filen ble ikke lagret",
        "error_lead": "Filen følger ikke agendamalen. Rett feilene og last opp på nytt.",
        "error_note": "closed og in_scope må alltid stå på hver sak – systemet gjetter aldri.",
        "err_ext": "Filen må ha endelsen .yaml, .yml, .pdf eller .docx.",
        "err_doc_size": "Filen er større enn 200 MB.",
        "err_doc_content": "Filen er ikke en gyldig PDF- eller Word-fil.",
        "err_meeting_id": "Møte-ID kan bare inneholde bokstaver a–z, tall, _, - og punktum.",
        "draft_h": "Kontroller sakslisten",
        "draft_lead": "Sakslisten er lest fra møteinnkallingen. Rett det som er feil, og velg "
                      "behandling for hver sak – systemet gjetter aldri.",
        "draft_meeting": "Møtet", "draft_save": "Lagre og kontroller",
        "col_handling": "Behandling", "h_choose": "Velg …", "suggested": "Foreslått",
        "handling": {"process": "Behandles", "closed": "Lukket sak",
                     "out_of_scope": "Utenfor omfang", "leave_out": "Utelat (fjern raden)"},
        "err_handling": "{case}: velg behandling.",
        "name_flag": "Tittelen kan inneholde et navn eller kontaktopplysninger. Bruk en rolle.",
        "papers_field": "Saksdokumenter (PDF) – valgfritt. Uten disse har sakene ingen vedlegg.",
        "draft_found": "saker funnet",
        "err_size": "Filen er større enn 200 KB.", "err_empty": "Ingen fil ble valgt.",
        "err_encoding": "Filen er ikke UTF-8-tekst.",
        "choose_other": "Velg en annen fil",
        "started_h": "Kjøringen er startet",
        "started_body": "Det kan ta noen minutter. Briefene dukker opp under Møter når de er "
                        "klare til gjennomgang. Stopper du UI-et før kjøringen er ferdig, går "
                        "den tapt.",
        "refresh": "Oppdater Møter", "not_found": "Fant ikke den opplastede filen.",
        # login
        "passphrase": "Passord",
        # how it works
        "how_lead": "For hver sak på sakslisten finner systemet avsnittene i vedleggene som "
                    "handler om saken, og legger dem fram ordrett med side og kapittel. Du "
                    "bestemmer hva som deles.",
        "who": {"sys": "Systemet", "model": "Språkmodell", "you": "Du"},
        "not_title": "Hva briefen ikke er",
        "not": ["Den oppsummerer, tolker eller anbefaler ikke. Utdragene er kopiert ordrett "
                "fra kilden.",
                "Den erstatter ikke dokumentene. Den er et supplement, med lenke til hver side.",
                "Lukkede saker behandles aldri, og ingen brief deles før du har godkjent den."],
        "steps": [
            ("Agendaen leses inn", "sys",
             "Agendafilen kontrolleres. Lukkede saker hoppes alltid over, og saker utenfor "
             "omfang logges og hoppes over.",
             "Vises under «Agenda (innlest)» på møtesiden."),
            ("Vedleggene hentes og deles opp", "sys",
             "PDF-ene lastes ned og deles i nummererte avsnitt med side, trykt sidetall og "
             "kapittel. Sider uten søkbar tekst merkes.",
             "Antall sider og vedlegg står på møtesiden."),
            ("Saken tolkes", "model",
             "En språkmodell skriver et kort tema og søkefraser på bokmål, nynorsk og engelsk. "
             "Tittelen søkes alltid i tillegg.",
             "Vises under «Tolkning», slik at du kan se om saken ble misforstått."),
            ("Relevante avsnitt søkes fram", "model",
             "Systemet søker og følger kryssreferanser. Modellen velger avsnitt ut fra nummer, "
             "men skriver aldri tekst selv.",
             "Hvert utdrag viser om det kom fra søk eller fra en henvisning."),
            ("Kontroll mot kilden", "sys",
             "Koden kopierer teksten og sjekker at den står ordrett på oppgitt side. Utdrag "
             "som ikke består, fjernes.",
             "Resultatet står øverst på hver sak."),
            ("Du går gjennom og godkjenner", "you",
             "Fjern eller flytt utdrag, skriv en merknad, velg språk og godkjenn. Bare "
             "godkjente briefer kan eksporteres.",
             "Alle handlinger lagres i loggen."),
        ],
    },
    "nn": {
        "org": "Møtesekretariatet · Innlandet fylkeskommune", "main_nav": "Hovudmeny",
        "meetings": "Møte", "how": "Slik verkar det", "lang_label": "Språk",
        "test_banner": "Testmiljø – ikkje i drift. Brief vert delte først etter godkjenning.",
        "crumb": "Brødsmular",
        "meetings_lead": "Køyringar som ventar på eller har fått gjennomgang. Nyaste først.",
        "no_runs": "Ingen køyringar enno. Last opp ein agenda for å starte.",
        "items_n": "saker", "approved_n": "godkjende", "awaiting_n": "ventar på gjennomgang",
        "extracts": "utdrag", "attachments_n": "vedlegg", "pages": "sider", "run": "Køyring",
        "written": "Målform", "brief_in": "brief på", "style": "stil",
        "approved_of": "av {n} saker godkjende",
        "upload_title": "Last opp agenda",
        "upload_lead": "Vel ei agendafil eller møteinnkallinga (PDF/Word). Ho vert kontrollert "
                       "før noko vert lagra, og du ser "
                       "korleis ho vart lesen før du startar køyringa.",
        "upload_field": "Agenda (.yaml/.yml maks 200 KB, eller møteinnkalling som .pdf/.docx)",
        "upload_button": "Last opp og kontroller",
        "example": "Last ned eksempelagenda (agenda.yaml)",
        "upload_note": "Vedlegga vert henta frå lenkjene i agendaen. Lukka saker vert aldri "
                       "handsama. Du kan òg leggje fila rett i mappa inbox/.",
        "share_pdf": "Del som PDF", "export_h": "Brief til møtet (PDF)",
        "export_lead": "Éin PDF med alle godkjende saker som du kan dele med deltakarane: "
                       "framside med sakliste og sidetal, ei kort orientering per sak og "
                       "alle utdrag som vedlegg.",
        "export_blocked": "Desse sakene må godkjennast eller avvisast før du kan lage PDF-en:",
        "export_ready": "Alle handsama saker er godkjende eller avviste.",
        "meeting_note": "Merknad til heile møtet (valfritt)",
        "pdf_language": "Språk i PDF-en",
        "confirm_pii": "Eg har kontrollert at utdraga ikkje inneheld personopplysningar.",
        "pii_warning": "Namn i løpande tekst vert ikkje oppdaga automatisk. Les gjennom "
                       "utdraga før du deler.",
        "download_pdf": "Last ned PDF", "in_pdf": "I PDF-en",
        "entry": {"approved": "brief", "rejected": "ingen brief", "closed": "lukka sak",
                  "procedural": "formalitet", "scope": "utanfor omfang"},
        "public_url": "Offentleg lenkje til møtet (valfritt)",
        "orientation": "Orientering", "orient_lead": "Det viktigaste per sak, kort og ordrett frå "
                       "sakspapira: kva som skal vedtakast, bakgrunn, konsekvensar, vurdering og "
                       "innspel. Sjå heile briefen for alle utdrag.",
        "not_approved": "Ikkje godkjend enno", "show_full": "Vis heile utdraget",
        "more_in_brief": "{n} til i heile briefen", "open_brief": "Heile briefen",
        "no_extracts_yet": "Ingen utdrag.", "why_h": "Kvifor dette utdraget?",
        "categories": {"decision": "Kva skal vedtakast", "background": "Kva saka gjeld",
                       "consequences": "Konsekvensar", "assessment": "Vurdering",
                       "input": "Innspel", "other": "Anna relevant"},
        "relevance": {"direct": "Direkte relevant", "supporting": "Støttande",
                      "cross_reference": "Kryssreferanse"},
        "start_review": "Start gjennomgang", "summary": "Samandrag",
        "stat_items": "saker på sakslista", "stat_awaiting": "ventar på gjennomgang",
        "stat_approved": "godkjende", "stat_checked": "utdrag bestod kontroll mot kjelda",
        "agenda_file": "Agendafil", "attachment": "Vedlegg", "show_raw": "Vis agendafila",
        "col1": "Agenda (innlesen)", "col2": "Tolking", "col3": "Brief (resultat)",
        "open": "open", "closed": "lukka", "in_scope": "i omfang", "out_scope": "utanfor omfang",
        "recommendation": "Innstilling", "topic": "Tema slik systemet forstod saka",
        "queries": "Søk som vart køyrde", "no_interp": "Inga tolking – saka vart ikkje søkt i.",
        "review": "Gå gjennom", "raw_title": "Agendafila slik ho vart lesen",
        "agenda_missing": "Agendafila er ikkje tilgjengeleg lenger.",
        "llm_calls": "LLM-kall", "tokens": "tokens", "seconds": "s",
        "halted": "Stoppa",
        "status": {"awaiting_review": "Ventar på gjennomgang", "approved": "Godkjend",
                   "rejected": "Avvist", "skipped": "Ikkje handsama", "halted": "Stoppa",
                   "draft_incomplete": "Ufullstendig utkast"},
        "types": {"procedural": "formalitet", "information": "orientering", "case": "sak",
                  "question": "spørsmål"},
        "items_in_meeting": "Saker i møtet", "verification": "Kontroll mot kjelda",
        "interpretation": "Slik systemet forstod saka", "actions": "Handlingar",
        "language": "Språk i brief", "approve": "Godkjenn brief", "reject": "Avvis",
        "export": "Eksporter", "only_approved": "Berre godkjende brief kan eksporterast.",
        "approved_msg": "Godkjend.", "note": "Merknad frå møtesekretariatet", "save": "Lagre",
        "extracts_h": "Utdrag", "extracts_sub": "ordrett frå kjelda, kan fjernast eller flyttast",
        "kept": "{kept} av {total} utdrag med i briefen", "up": "Flytt opp", "down": "Flytt ned",
        "remove": "Fjern", "restore": "Gjenopprett", "removed": "Fjerna", "page": "side",
        "printed": "trykt", "open_pdf": "opne PDF på sida", "table_header": "Tabelloverskrift",
        "page_preview": "Førehandsvising av side", "audit": "Logg",
        "no_audit": "Ingen handlingar enno.", "nothing": "Ingen utdrag.",
        "lang_names": {"nb": "bokmål", "nn": "nynorsk", "en": "engelsk"},
        "valid_h": "Agendaen er gyldig", "saved_as": "Lagra som", "cancel": "Avbryt",
        "start_run": "Start køyring", "meeting_read": "Møtet slik det vart lese",
        "body": "Organ", "date": "Dato", "meeting_id": "Møte-ID", "authority": "Styresmakt",
        "unique_att": "Vedlegg å hente", "items_h": "Saker",
        "to_process": "vert handsama", "to_skip": "vert hoppa over",
        "col_case": "Sak", "col_type": "Type", "col_title": "Tittel",
        "col_att": "Vedlegg", "col_process": "Handsamast?", "yes": "Ja",
        "skip": {"closed": "Nei – lukka sak", "procedural": "Nei – formalitet",
                 "scope": "Nei – utanfor omfang"},
        "error_h": "Fila vart ikkje lagra",
        "error_lead": "Fila følgjer ikkje agendamalen. Rett feila og last opp på nytt.",
        "error_note": "closed og in_scope må alltid stå på kvar sak – systemet gjettar aldri.",
        "err_ext": "Fila må ha endinga .yaml, .yml, .pdf eller .docx.",
        "err_doc_size": "Fila er større enn 200 MB.",
        "err_doc_content": "Fila er ikkje ei gyldig PDF- eller Word-fil.",
        "err_meeting_id": "Møte-ID kan berre innehalde bokstavane a–z, tal, _, - og punktum.",
        "draft_h": "Kontroller sakslista",
        "draft_lead": "Sakslista er lesen frå møteinnkallinga. Rett det som er feil, og vel "
                      "handsaming for kvar sak – systemet gjettar aldri.",
        "draft_meeting": "Møtet", "draft_save": "Lagre og kontroller",
        "col_handling": "Handsaming", "h_choose": "Vel …", "suggested": "Føreslått",
        "handling": {"process": "Vert handsama", "closed": "Lukka sak",
                     "out_of_scope": "Utanfor omfang", "leave_out": "Utelat (fjern rada)"},
        "err_handling": "{case}: vel handsaming.",
        "name_flag": "Tittelen kan innehalde eit namn eller kontaktopplysningar. Bruk ei rolle.",
        "papers_field": "Saksdokument (PDF) – valfritt. Utan dei har sakene ingen vedlegg.",
        "draft_found": "saker funne",
        "err_size": "Fila er større enn 200 KB.", "err_empty": "Inga fil vart vald.",
        "err_encoding": "Fila er ikkje UTF-8-tekst.",
        "choose_other": "Vel ei anna fil",
        "started_h": "Køyringa er starta",
        "started_body": "Det kan ta nokre minutt. Briefane dukkar opp under Møte når dei er "
                        "klare til gjennomgang. Stoppar du UI-et før køyringa er ferdig, går "
                        "ho tapt.",
        "refresh": "Oppdater Møte", "not_found": "Fann ikkje den opplasta fila.",
        "passphrase": "Passord",
        "how_lead": "For kvar sak på sakslista finn systemet avsnitta i vedlegga som handlar "
                    "om saka, og legg dei fram ordrett med side og kapittel. Du avgjer kva som "
                    "vert delt.",
        "who": {"sys": "Systemet", "model": "Språkmodell", "you": "Du"},
        "not_title": "Kva briefen ikkje er",
        "not": ["Han samanfattar, tolkar eller tilrår ikkje. Utdraga er kopierte ordrett frå "
                "kjelda.",
                "Han erstattar ikkje dokumenta. Han er eit supplement, med lenkje til kvar side.",
                "Lukka saker vert aldri handsama, og ingen brief vert delt før du har godkjent "
                "han."],
        "steps": [
            ("Agendaen vert lesen inn", "sys",
             "Agendafila vert kontrollert. Lukka saker vert alltid hoppa over, og saker utanfor "
             "omfang vert logga og hoppa over.",
             "Vist under «Agenda (innlesen)» på møtesida."),
            ("Vedlegga vert henta og delte opp", "sys",
             "PDF-ane vert lasta ned og delte i nummererte avsnitt med side, trykt sidetal og "
             "kapittel. Sider utan søkbar tekst vert merkte.",
             "Tal på sider og vedlegg står på møtesida."),
            ("Saka vert tolka", "model",
             "Ein språkmodell skriv eit kort tema og søkjefrasar på bokmål, nynorsk og engelsk. "
             "Tittelen vert alltid søkt i tillegg.",
             "Vist under «Tolking», slik at du kan sjå om saka vart misforstått."),
            ("Relevante avsnitt vert søkte fram", "model",
             "Systemet søkjer og følgjer kryssreferansar. Modellen vel avsnitt ut frå nummer, "
             "men skriv aldri tekst sjølv.",
             "Kvart utdrag viser om det kom frå søk eller frå ei tilvising."),
            ("Kontroll mot kjelda", "sys",
             "Koden kopierer teksten og sjekkar at han står ordrett på oppgitt side. Utdrag som "
             "ikkje består, vert fjerna.",
             "Resultatet står øvst på kvar sak."),
            ("Du går gjennom og godkjenner", "you",
             "Fjern eller flytt utdrag, skriv ein merknad, vel språk og godkjenn. Berre "
             "godkjende brief kan eksporterast.",
             "Alle handlingar vert lagra i loggen."),
        ],
    },
    "en": {
        "org": "Meeting secretariat · Innlandet County Council", "main_nav": "Main menu",
        "meetings": "Meetings", "how": "How it works", "lang_label": "Language",
        "test_banner": "Test environment – not in service. Briefs are shared only after "
                       "approval.",
        "crumb": "Breadcrumb",
        "meetings_lead": "Runs awaiting or finished with review. Newest first.",
        "no_runs": "No runs yet. Upload an agenda to start.",
        "items_n": "items", "approved_n": "approved", "awaiting_n": "awaiting review",
        "extracts": "extracts", "attachments_n": "attachments", "pages": "pages", "run": "Run",
        "written": "Written standard", "brief_in": "brief in", "style": "style",
        "approved_of": "of {n} items approved",
        "upload_title": "Upload agenda",
        "upload_lead": "Choose an agenda file or the meeting notice (PDF/Word). It is checked "
                       "before anything is saved, and you "
                       "see how it was read before you start the run.",
        "upload_field": "Agenda (.yaml/.yml, max 200 KB, or meeting notice as .pdf/.docx)",
        "upload_button": "Upload and check",
        "example": "Download example agenda (agenda.yaml)",
        "upload_note": "Attachments are fetched from the links in the agenda. Closed items are "
                       "never processed. You can also drop the file into the inbox/ folder.",
        "share_pdf": "Share as PDF", "export_h": "Meeting brief (PDF)",
        "export_lead": "One PDF with every approved item to share with participants: a front "
                       "page with the item list and page numbers, a short orientation per "
                       "item and all extracts as an appendix.",
        "export_blocked": "These items must be approved or rejected before the PDF can be made:",
        "export_ready": "Every processed item is approved or rejected.",
        "meeting_note": "Note for the whole meeting (optional)",
        "pdf_language": "PDF language",
        "confirm_pii": "I have checked that the extracts contain no personal data.",
        "pii_warning": "Names in running text are not detected automatically. Read the "
                       "extracts before sharing.",
        "download_pdf": "Download PDF", "in_pdf": "In the PDF",
        "entry": {"approved": "brief", "rejected": "no brief", "closed": "closed item",
                  "procedural": "procedural", "scope": "out of scope"},
        "public_url": "Public link to the meeting (optional)",
        "orientation": "Orientation", "orient_lead": "The essentials per item, short and "
                       "verbatim from the case papers: what is to be decided, background, "
                       "consequences, assessment and input. See the full brief for all extracts.",
        "not_approved": "Not approved yet", "show_full": "Show the whole extract",
        "more_in_brief": "{n} more in the full brief", "open_brief": "Full brief",
        "no_extracts_yet": "No extracts.", "why_h": "Why this extract?",
        "categories": {"decision": "What is to be decided", "background": "What the item is about",
                       "consequences": "Consequences", "assessment": "Assessment",
                       "input": "Input", "other": "Other relevant"},
        "relevance": {"direct": "Directly relevant", "supporting": "Supporting",
                      "cross_reference": "Cross-reference"},
        "start_review": "Start review", "summary": "Summary",
        "stat_items": "items on the agenda", "stat_awaiting": "awaiting review",
        "stat_approved": "approved", "stat_checked": "extracts passed the source check",
        "agenda_file": "Agenda file", "attachment": "Attachment", "show_raw": "Show agenda file",
        "col1": "Agenda (as read)", "col2": "Interpretation", "col3": "Brief (output)",
        "open": "open", "closed": "closed", "in_scope": "in scope", "out_scope": "out of scope",
        "recommendation": "Recommendation", "topic": "Topic as the system understood it",
        "queries": "Searches run", "no_interp": "No interpretation – the item was not searched.",
        "review": "Review", "raw_title": "The agenda file as read",
        "agenda_missing": "The agenda file is no longer available.",
        "llm_calls": "LLM calls", "tokens": "tokens", "seconds": "s",
        "halted": "Halted",
        "status": {"awaiting_review": "Awaiting review", "approved": "Approved",
                   "rejected": "Rejected", "skipped": "Not processed", "halted": "Halted",
                   "draft_incomplete": "Incomplete draft"},
        "types": {"procedural": "procedural", "information": "information", "case": "case",
                  "question": "question"},
        "items_in_meeting": "Items in the meeting", "verification": "Source check",
        "interpretation": "How the system understood the item", "actions": "Actions",
        "language": "Brief language", "approve": "Approve brief", "reject": "Reject",
        "export": "Export", "only_approved": "Only approved briefs can be exported.",
        "approved_msg": "Approved.", "note": "Organiser's note", "save": "Save",
        "extracts_h": "Extracts", "extracts_sub": "verbatim from the source; remove or reorder",
        "kept": "{kept} of {total} extracts in the brief", "up": "Move up", "down": "Move down",
        "remove": "Remove", "restore": "Restore", "removed": "Removed", "page": "page",
        "printed": "printed", "open_pdf": "open PDF at this page", "table_header": "Table header",
        "page_preview": "Preview of page", "audit": "Log",
        "no_audit": "No actions yet.", "nothing": "No extracts.",
        "lang_names": {"nb": "Bokmål", "nn": "Nynorsk", "en": "English"},
        "valid_h": "The agenda is valid", "saved_as": "Saved as", "cancel": "Cancel",
        "start_run": "Start run", "meeting_read": "The meeting as read",
        "body": "Body", "date": "Date", "meeting_id": "Meeting ID", "authority": "Authority",
        "unique_att": "Attachments to fetch", "items_h": "Items",
        "to_process": "processed", "to_skip": "skipped",
        "col_case": "Item", "col_type": "Type", "col_title": "Title",
        "col_att": "Attachments", "col_process": "Processed?", "yes": "Yes",
        "skip": {"closed": "No – closed item", "procedural": "No – procedural",
                 "scope": "No – out of scope"},
        "error_h": "The file was not saved",
        "error_lead": "The file does not follow the agenda template. Fix the errors and upload "
                      "again.",
        "error_note": "closed and in_scope must be present on every item – the system never "
                      "guesses.",
        "err_ext": "The file must end in .yaml, .yml, .pdf or .docx.",
        "err_doc_size": "The file is larger than 200 MB.",
        "err_doc_content": "The file is not a valid PDF or Word file.",
        "err_meeting_id": "Meeting ID may only contain letters a–z, digits, _, - and dots.",
        "draft_h": "Check the agenda",
        "draft_lead": "The agenda was read from the meeting notice. Correct anything wrong, and "
                      "choose a handling for every item – the system never guesses.",
        "draft_meeting": "The meeting", "draft_save": "Save and check",
        "col_handling": "Handling", "h_choose": "Choose …", "suggested": "Suggested",
        "handling": {"process": "Process", "closed": "Closed item",
                     "out_of_scope": "Out of scope", "leave_out": "Leave out (remove row)"},
        "err_handling": "{case}: choose a handling.",
        "name_flag": "The title may contain a name or contact details. Use a role instead.",
        "papers_field": "Case papers (PDF) – optional. Without them the items have no "
                        "attachments.",
        "draft_found": "items found",
        "err_size": "The file is larger than 200 KB.", "err_empty": "No file was chosen.",
        "err_encoding": "The file is not UTF-8 text.",
        "choose_other": "Choose another file",
        "started_h": "The run has started",
        "started_body": "This can take a few minutes. The briefs appear under Meetings when "
                        "they are ready for review. If you stop the UI before the run "
                        "finishes, the run is lost.",
        "refresh": "Refresh Meetings", "not_found": "The uploaded file was not found.",
        "passphrase": "Passphrase",
        "how_lead": "For each item on the agenda, the system finds the passages in the "
                    "attachments that concern it and shows them verbatim with page and "
                    "section. You decide what is shared.",
        "who": {"sys": "System", "model": "Language model", "you": "You"},
        "not_title": "What the brief is not",
        "not": ["It does not summarise, interpret or recommend. Extracts are copied verbatim "
                "from the source.",
                "It does not replace the documents. It is a supplement, with a link to every "
                "page.",
                "Closed items are never processed, and no brief is shared until you approve "
                "it."],
        "steps": [
            ("The agenda is read", "sys",
             "The agenda file is validated. Closed items are always skipped; out-of-scope "
             "items are logged and skipped.",
             "Shown under “Agenda (as read)” on the meeting page."),
            ("Attachments are fetched and split", "sys",
             "The PDFs are downloaded and split into numbered passages with page, printed page "
             "number and section. Pages with no searchable text are flagged.",
             "Page and attachment counts are on the meeting page."),
            ("The item is interpreted", "model",
             "A language model writes a short topic and search phrases in Bokmål, Nynorsk and "
             "English. The title is always searched as well.",
             "Shown under “Interpretation”, so you can spot a misunderstanding."),
            ("Relevant passages are found", "model",
             "The system searches and follows cross-references. The model picks passages by "
             "number but never writes text itself.",
             "Each extract shows whether it came from search or a reference."),
            ("Checked against the source", "sys",
             "Code copies the text and checks it appears verbatim on the cited page. Extracts "
             "that fail are removed.",
             "The result is shown at the top of each item."),
            ("You review and approve", "you",
             "Remove or reorder extracts, add a note, choose the language and approve. Only "
             "approved briefs can be exported.",
             "Every action is saved in the log."),
        ],
    },
}
