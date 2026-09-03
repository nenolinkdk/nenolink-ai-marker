# Nenolink AI Marker - Brugervejledning

Applikationsversion: 0.5.0<br>
Dokumentsprog: Dansk  
Opdateret: 2. september 2026  
Udgiver: Nenolink  
Danmark

## 1. Hvad Nenolink AI Marker gør

Nenolink AI Marker tilføjer et synligt oplysningsbadge til billeder og, når FFmpeg er installeret, videoer. Programmet understøtter enkelte billeder og gentagelige mappebehandlinger. Originaler overskrives aldrig bevidst; outputnavne slutter med `_ai`.

Nenolinks badgesystem er et praktisk transparenssystem. Vælg den formulering, der præcist beskriver, hvordan AI indgik i det konkrete indhold eller arbejdsforløb.

## AI Marker-metadata

Nenolink AI Marker tilføjer automatisk minimale maskinlæsbare metadata til behandlede filer. De identificerer Nenolink AI Marker som softwaren, registrerer det valgte AI-mærke og markeringsversionen. Metadata supplerer det synlige badge; det synlige badge er fortsat den primære menneskeligt læsbare oplysning.

Metadata er ikke et bevis på ægthed, er ikke manipulationssikre og garanterer ikke juridisk eller lovgivningsmæssig overholdelse. Redigeringssoftware, websites og sociale medieplatforme kan ændre eller fjerne metadata. Kontrollér hvert behandlet output før offentliggørelse, og behold originalfilen.

> **Juridisk meddelelse:** Nenolink AI Marker er et praktisk værktøj til transparens og mærkning. Dets badges og dokumentation er ikke juridisk rådgivning, certificering, myndighedsgodkendelse eller en garanti for overholdelse af EU's AI-forordning eller andre krav. Brugeren er ansvarlig for at vælge passende oplysninger, kontrollere output og overholde gældende lovgivning, aftaler, platformregler og faglige krav. Se den fulde Juridiske meddelelse og ansvarsfraskrivelse sidst i vejledningen.

## 2. Installation og første start

Udpak hele Windows ZIP-filen til en mappe, du kan skrive til. Behold EXE-filen, `assets`, `locales` og `docs` samlet. Start `Nenolink-AI-Marker.exe`. Windows kan vise en omdømmeadvarsel for en usigneret download; kontrollér, at filen kommer fra den officielle Nenolink-udgivelse, før du fortsætter.

Programmet kræver ikke administratorrettigheder. Indstillinger gemmes under `%APPDATA%\Nenolink\AI Marker\settings.json`, så en udskiftning af programmappen normalt ikke fjerner præferencer.

## 3. Sprogvalg

Vælg sprog i topbjælken. Engelsk, dansk, tysk, fransk, spansk, italiensk, portugisisk, nederlandsk, svensk, norsk, polsk og tjekkisk medfølger. Valget gemmes med det samme. Manglende oversættelser falder tilbage til engelsk. Produktnavnet og badgegrafikken ændres ikke med grænsefladens sprog.

## 4. Standardmapper og egne badgemapper

Åbn **Badges**. **Nenolink Standard Badges** bruger de ti filer i `assets\badges`. Hvis du vil bruge din egen transparente PNG-fil, skal du vælge **Egen badgemappe**, vælge en mappe og klikke på **Opdater badges**, når du har tilføjet filer. Programmet læser egne filer på stedet og kopierer eller ændrer dem ikke. Hvis en gemt mappe forsvinder, viser programmet den nøjagtige sti og bruger midlertidigt standardbadges, mens den gamle sti bevares, så den kan rettes.

## 5. Valg af badge

Vælg et badge i badgemenuen. Det samme valgte badge bruges i forhåndsvisningen af enkeltbilleder, i gemte billeder og på alle valgte elementer i en mappebehandling. En opdatering bevarer valget, når filen stadig findes.

## 6. Forhåndsvisning af badge

Badgevisningen viser badget uden at strække det. Standardbadges viser også et læsbart navn. Gennemsigtighed og billedformat bevares. Du kan også vælge et badge i galleriet på fanen **Badges**.

## 7. Behandling af et enkelt billede

Vælg **Enkelt fil** og derefter **Vælg billede**. JPG, JPEG, PNG og WebP understøttes. Juster placeringen, og kontrollér forhåndsvisningen. Klik på **Behandl billede**, vælg en outputmappe, og kontrollér afslutningsmeddelelsen. Originalen i fuld opløsning bruges til det endelige output; forhåndsvisningen er kun en skaleret visning.

## 8. Behandling af video

Videobehandling i mapper accepterer MP4, MOV, MKV, AVI og WebM. Det kræver et særskilt installeret `ffmpeg`-program, som er tilgængeligt på Windows `PATH`. Lyd kopieres, når den valgte outputcontainer tillader det. Kodningen bruger H.264. Kombinationer af container og codec varierer; afprøv et output før offentliggørelse. Hvis FFmpeg mangler eller afviser en fil, registreres filen som en fejl, og behandlingen fortsætter.

## 9. Mappebehandling

Vælg **Batchbehandling**, vælg en inputmappe, konfigurer output og filindstillinger, og klik derefter på **Scan mappe**. Kontrollér antallet af billeder, videoer, ikke-understøttede filer, valgte filer og destinationen. Klik først på **Start batchbehandling**, når scanningen er kontrolleret. Status viser det aktuelle filnavn samt antal succeser, spring og fejl. **Annuller batch** stopper før næste fil; allerede færdige output slettes ikke. En beskadiget fil stopper ikke senere filer.

## 10. Input- og outputmapper

Standardoutput er en redigerbar undermappe med navnet `AI-marked` i inputmappen. Du kan i stedet vælge en særskilt outputmappe. **Medtag undermapper** scanner rekursivt. **Bevar mappestruktur** genskaber relative mapper under destinationen. Eksisterende outputfiler springes over og overskrives aldrig. Outputnavngivningen er `originalnavn_ai.ext`.

## 11. Placering, størrelse, margen og opacitet

Placeringen kan være øverst til venstre, øverst til højre, nederst til venstre eller nederst til højre. Størrelsen er en procentdel af billedets bredde. Margenen måles i kildebilledets pixels fra de valgte kanter. Opaciteten går fra helt gennemsigtig til helt dækkende. Programmet begrænser ekstreme indstillinger, så badget forbliver inden for mediets ramme.

## 12. Valg af det rette standardbadge

De første fire badges beskriver en overordnet oplysningsstatus. De resterende seks beskriver en medietype eller arbejdsgang. Et badge er et kort signal, ikke en fuldstændig dokumentation af oprindelse. Bevar supplerende oplysninger, når sammenhængen kræver det.

### 13. AI Assisted

Anbefales, når AI har bidraget, men en person fortsat har været væsentligt involveret i planlægning, udvælgelse, redigering eller forfatterskab.

### 14. AI Generated

Anbefales, når et AI-system hovedsageligt har genereret indholdet. Menneskelig prompting eller udvælgelse betyder ikke i sig selv, at outputtet ikke er AI-genereret.

### 15. AI Modified

Anbefales, når AI væsentligt har ændret eksisterende indhold, for eksempel gennem omfattende udfyldning, erstatning, syntese eller transformation.

### 16. Human Reviewed

Anbefales som en yderligere oplysning, når en person har kontrolleret AI-relateret output før offentliggørelse. En kontrol garanterer ikke korrekthed, sikkerhed, lovlighed eller overholdelse af regler.

### 17. AI Image

Anbefales ved AI-specifik generering eller væsentlig ændring af billedindhold.

### 18. AI Video

Anbefales ved AI-specifik generering eller væsentlig ændring af videoindhold.

### 19. AI Audio

Anbefales til syntetisk eller væsentligt AI-ændret tale, musik, lyd eller andet lydindhold.

### 20. AI Software

Anbefales, når AI væsentligt har bidraget til produktion af software eller kildekode. Badget er ikke en sikkerheds- eller kvalitetscertificering.

### 21. AI Translation

Anbefales, når AI har oversat indhold mellem sprog. Overvej menneskelig kontrol af betydningsfuldt eller specialiseret materiale.

### 22. AI Localization

Anbefales, når AI har bidraget til at tilpasse indhold til et lokalområde, marked eller en kultur ud over direkte oversættelse.

## 23. Baggrund om transparens i EU's AI-forordning

Forordning (EU) 2024/1689, almindeligvis kaldet EU's AI-forordning, indeholder transparensforpligtelser for udbydere og idriftsættere af visse AI-systemer. Artikel 50 omhandler blandt andet information til personer, når de interagerer med visse AI-systemer, maskinlæsbar mærkning af syntetisk output fra udbydere samt oplysningspligt ved visse deepfakes og tekster af offentlig interesse. De præcise pligter, undtagelser, tidspunkter, tekniske standarder og ansvarlige parter afhænger af de konkrete forhold og gældende ret.

Nenolink AI Marker tilføjer et synligt badge. Et synligt badge er ikke det samme som enhver maskinlæsbar mærkning eller oplysning, som artikel 50 kan kræve. Ikke alle Nenolink-badges er individuelt påkrævet af EU's AI-forordning, og brug af programmet sikrer ikke automatisk overholdelse. Se den officielle forordning, og indhent kvalificeret juridisk rådgivning om din situation.

Officiel kilde: Forordning (EU) 2024/1689, artikel 50, EUR-Lex: https://eur-lex.europa.eu/legal-content/DA/TXT/?uri=CELEX:32024R1689

## 24. Filkompatibilitet og behandlingsgrænser

Som praktisk vejledning anbefales billeder op til 50 MB og videoer op til 2 GB. Det er anbefalinger, ikke garanterede tekniske maksimumgrænser; større filer kan stadig fungere.

Ikke alle billed- eller videofiler kan nødvendigvis behandles. Kompatibilitet og praktiske behandlingsgrænser afhænger af filformat, codec, opløsning, varighed, filstørrelse, om filen er beskadiget eller korrupt, usædvanlig kodning, tilgængelig RAM, CPU-ydelse, ledig diskplads og plads til midlertidig behandling. Videobehandling afhænger også af den installerede FFmpeg-version, og om FFmpeg understøtter filens container, codecs og kodning.

Der fastsættes ikke en bestemt maksimal filstørrelse. En fil, der virker på én computer, kan fejle eller tage betydeligt længere tid på en anden, fordi de praktiske grænser delvist afhænger af brugerens computer og tilgængelige ressourcer. Bevar originalfiler, og kontrollér hvert behandlet output før offentliggørelse eller distribution.

## 25. Begrænsninger og brugerens ansvar

Du er ansvarlig for at vælge et korrekt badge, indhente rettigheder til kildemedier og badgegrafik, kontrollere output, bevare originaler og overholde gældende aftaler, platformregler samt krav om tilgængelighed, privatliv, immaterielle rettigheder, forbrugerbeskyttelse og AI. Synlige overlays kan beskæres eller fjernes. Værktøjet indlejrer ikke kryptografisk oprindelsesdokumentation og kontrollerer ikke, om indhold er fremstillet med AI.

## Juridisk meddelelse og ansvarsfraskrivelse

Nenolink AI Marker er et softwareværktøj, der er udviklet til at hjælpe brugere med at give gennemsigtige oplysninger om brugen af kunstig intelligens i digitalt indhold og produktionsprocesser.

De badges, beskrivelser, anbefalinger og den dokumentation, som leveres med softwaren, udgør et praktisk transparens- og mærkningssystem udviklet af Nenolink. De udgør ikke juridisk rådgivning, certificering, myndighedsgodkendelse eller en garanti for overholdelse af forordning (EU) 2024/1689 (Den Europæiske Unions forordning om kunstig intelligens) eller anden gældende lovgivning eller regulering.

Ikke alle Nenolink AI-badges svarer til et bestemt lovbestemt mærkningskrav. Nogle badges stilles frivilligt til rådighed for at understøtte større gennemsigtighed om, hvordan AI er blevet anvendt.

De relevante oplysnings- eller mærkningskrav afhænger af indholdet, det anvendte AI-system, brugerens rolle, den sammenhæng, hvori indholdet offentliggøres, og gældende lovgivning.

Brugerne er fortsat ansvarlige for at afgøre, om og hvordan deres indhold skal mærkes, og for at overholde gældende lovgivning, kontraktlige forpligtelser, platformregler og faglige krav.

Henvisninger til EU's AI-forordning og andet regulatorisk materiale gives alene til generel information. Lovgivning, myndighedsvejledning og fortolkninger kan ændre sig over tid. Brugere bør konsultere aktuelle officielle kilder og om nødvendigt indhente relevant faglig eller juridisk rådgivning.

Nenolink garanterer ikke, at anvendelsen af et badge med Nenolink AI Marker i sig selv opfylder et bestemt juridisk, regulatorisk eller kontraktligt oplysningskrav.

Softwareoutput bør kontrolleres af brugeren før offentliggørelse eller distribution.

Nenolink AI Marker må ikke præsenteres som:

- et EU-certificeret complianceværktøj;
- et automatiseret system til overholdelse af EU's AI-forordning;
- juridisk rådgivning; eller
- en garanti for, at indhold er korrekt klassificeret.

## 26. Fejlfinding

- **Ingen badges fundet:** Kontrollér, at PNG-filer ligger direkte i den viste mappe, og klik derefter på **Opdater badges**.
- **Egen mappe mangler:** Tilslut drevet igen, eller vælg en erstatningsmappe. Standardbadges er fortsat tilgængelige.
- **Billedet kan ikke åbnes:** Kontrollér, at det er en gyldig JPG-, JPEG-, PNG- eller WebP-fil og ikke blot har fået et nyt filnavn.
- **En stor eller kompleks fil fejler:** Luk andre krævende programmer, kontrollér tilgængelig RAM og ledig diskplads, og prøv en kopi i lavere opløsning, mens originalen bevares.
- **Beskadiget eller usædvanligt kodet fil:** Åbn og eksporter en kopi i et almindeligt format med et pålideligt redigeringsprogram, og behandl derefter kopien. Kassér aldrig originalen.
- **Video fejler:** Kør `ffmpeg -version` i Kommandoprompt, kontrollér, at FFmpeg findes på `PATH`, og kontrollér, at FFmpeg understøtter containeren og codecs. Meget lange videoer, høj opløsning eller usædvanlig kodning kan kræve betydelig CPU, RAM, diskplads og midlertidig plads.
- **Behandlingen stopper, eller disken fyldes:** Frigør diskplads, herunder plads til midlertidig behandling, og prøv igen. Gennemse hele resultatfilen før offentliggørelse eller distribution.
- **PDF-vejledningen åbner ikke:** Kontrollér, at `docs\Nenolink-AI-Marker-User-Guide-DA.pdf` eller den engelske fallback ligger i programstrukturen, og at Windows har en standard-PDF-fremviser.
- **Uventet outputplacering:** Scan igen efter ændring af input- eller outputindstillinger, og læs den viste destination.
- **Eksisterende output springes over:** Omdøb eller flyt den eksisterende `_ai`-fil. Programmet overskriver den ikke.
- **Indstillinger virker beskadigede:** Luk programmet, sikkerhedskopiér og fjern `%APPDATA%\Nenolink\AI Marker\settings.json`; standardindstillinger oprettes ved næste start.

## Support og kreditering

Nenolink AI Marker - (c) Henrik Nielsen - https://nenolink.com
