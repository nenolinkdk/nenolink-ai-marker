import fs from "node:fs";
import path from "node:path";
const root = path.resolve(import.meta.dirname, "..", "locales");
const common = {
  "tab.single":"Single image", "tab.batch":"Folder batch", "tab.badges":"Badge settings",
  "button.user_guide":"User Guide (PDF)", "button.choose_badge_folder":"Choose Badge Folder",
  "button.choose_input":"Choose Input Folder", "button.choose_output":"Choose Output Folder",
  "button.scan_folder":"Scan Folder", "button.start_batch":"Start Batch Processing", "button.cancel_batch":"Cancel Batch",
  "badge.custom_description":"Custom badge image", "batch.input":"Input Folder",
  "batch.output_subfolder":"Create output subfolder inside input folder", "batch.output_separate":"Use separate output folder",
  "batch.recursive":"Include subfolders", "batch.preserve":"Preserve folder structure", "batch.images":"Process images",
  "batch.videos":"Process videos", "batch.skip":"Skip files that appear already processed",
  "batch.invalid_input":"Input folder does not exist: {folder}", "batch.scan_first":"Choose and scan an input folder before starting batch processing.",
  "batch.scan_summary":"Images: {images} | Videos: {videos} | Unsupported: {unsupported} | Total selected: {total}\nOutput: {output}",
  "batch.progress":"Current: {name} | Completed: {completed}/{total} | Successful: {success} | Skipped: {skipped} | Errors: {errors}",
  "batch.done":"Batch complete. Successful: {success}, skipped: {skipped}, errors: {errors}.", "batch.cancelled":"Batch cancelled.",
  "guide.missing":"The local user guide could not be opened. {error}", "error.title":"Error"
};
const translated = {
 da:{"button.user_guide":"Brugervejledning (PDF)","button.choose_badge_folder":"Vælg badge-mappe","button.choose_input":"Vælg inputmappe","button.choose_output":"Vælg outputmappe","button.scan_folder":"Scan mappe","button.start_batch":"Start batchbehandling","button.cancel_batch":"Annuller batch"},
 de:{"button.user_guide":"Benutzerhandbuch (PDF)","button.choose_badge_folder":"Badge-Ordner auswählen","button.choose_input":"Eingabeordner auswählen","button.choose_output":"Ausgabeordner auswählen","button.scan_folder":"Ordner scannen","button.start_batch":"Stapelverarbeitung starten","button.cancel_batch":"Stapel abbrechen"},
 fr:{"button.user_guide":"Guide d'utilisation (PDF)","button.choose_badge_folder":"Choisir le dossier des badges","button.choose_input":"Choisir le dossier d'entrée","button.choose_output":"Choisir le dossier de sortie","button.scan_folder":"Analyser le dossier","button.start_batch":"Démarrer le traitement par lot","button.cancel_batch":"Annuler le lot"},
 es:{"button.user_guide":"Guía del usuario (PDF)","button.choose_badge_folder":"Elegir carpeta de insignias","button.choose_input":"Elegir carpeta de entrada","button.choose_output":"Elegir carpeta de salida","button.scan_folder":"Examinar carpeta","button.start_batch":"Iniciar procesamiento por lotes","button.cancel_batch":"Cancelar lote"},
 it:{"button.user_guide":"Guida utente (PDF)","button.choose_badge_folder":"Scegli cartella badge","button.choose_input":"Scegli cartella di input","button.choose_output":"Scegli cartella di output","button.scan_folder":"Analizza cartella","button.start_batch":"Avvia elaborazione batch","button.cancel_batch":"Annulla batch"},
 pt:{"button.user_guide":"Guia do utilizador (PDF)","button.choose_badge_folder":"Escolher pasta de selos","button.choose_input":"Escolher pasta de entrada","button.choose_output":"Escolher pasta de saída","button.scan_folder":"Analisar pasta","button.start_batch":"Iniciar processamento em lote","button.cancel_batch":"Cancelar lote"},
 nl:{"button.user_guide":"Gebruikershandleiding (PDF)","button.choose_badge_folder":"Badgemap kiezen","button.choose_input":"Invoermap kiezen","button.choose_output":"Uitvoermap kiezen","button.scan_folder":"Map scannen","button.start_batch":"Batchverwerking starten","button.cancel_batch":"Batch annuleren"},
 sv:{"button.user_guide":"Användarhandbok (PDF)","button.choose_badge_folder":"Välj märkesmapp","button.choose_input":"Välj indatamapp","button.choose_output":"Välj utdatamapp","button.scan_folder":"Skanna mapp","button.start_batch":"Starta batchbearbetning","button.cancel_batch":"Avbryt batch"},
 no:{"button.user_guide":"Brukerveiledning (PDF)","button.choose_badge_folder":"Velg merkemappe","button.choose_input":"Velg inndatamappe","button.choose_output":"Velg utdatamappe","button.scan_folder":"Skann mappe","button.start_batch":"Start satsvis behandling","button.cancel_batch":"Avbryt sats"},
 pl:{"button.user_guide":"Podręcznik użytkownika (PDF)","button.choose_badge_folder":"Wybierz folder odznak","button.choose_input":"Wybierz folder wejściowy","button.choose_output":"Wybierz folder wyjściowy","button.scan_folder":"Skanuj folder","button.start_batch":"Rozpocznij przetwarzanie wsadowe","button.cancel_batch":"Anuluj wsad"},
 cs:{"button.user_guide":"Uživatelská příručka (PDF)","button.choose_badge_folder":"Vybrat složku odznak","button.choose_input":"Vybrat vstupní složku","button.choose_output":"Vybrat výstupní složku","button.scan_folder":"Prohledat složku","button.start_batch":"Spustit dávkové zpracování","button.cancel_batch":"Zrušit dávku"}
};
for (const file of fs.readdirSync(root).filter(f=>f.endsWith(".json"))) {
  const code=path.basename(file,".json"), full=path.join(root,file), data=JSON.parse(fs.readFileSync(full,"utf8"));
  Object.assign(data,common,translated[code]||{}); fs.writeFileSync(full,JSON.stringify(data,null,2)+"\n","utf8");
}
