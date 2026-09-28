import 'package:flutter/widgets.dart';

/// Five UI languages. Italian is the original copy; the others follow it.
class AppText extends InheritedWidget {
  const AppText({super.key, required this.s, required super.child});

  final S s;

  static S of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppText>();
    if (scope != null) return scope.s;
    return S(S.pick(Localizations.maybeLocaleOf(context)?.languageCode));
  }

  @override
  bool updateShouldNotify(AppText oldWidget) => oldWidget.s.code != s.code;
}

class S {
  S(String code) : code = pick(code);

  final String code;

  static const codes = ['it', 'en', 'fr', 'de', 'es'];

  static const names = {
    'it': 'Italiano',
    'en': 'English',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
  };

  static String pick(String? code) {
    final lang = (code ?? '').toLowerCase().split(RegExp('[-_]')).first;
    return codes.contains(lang) ? lang : 'en';
  }

  static Map<String, String> catalog(String code) => _catalogs[pick(code)]!;

  String t(String key) => _catalogs[code]![key] ?? _catalogs['en']![key] ?? key;

  String notificationsActive(String account) => t('notificationsActive').replaceAll('{account}', account);

  String folderCount(String folder, int n) {
    final word = n == 1 ? t('mailOne') : t('mailMany');
    return '· $folder: $n $word';
  }

  String get navModel => t('navModel');
  String get navMailboxes => t('navMailboxes');
  String get navService => t('navService');
  String get language => t('language');
  String get release => t('release');
  String updateTitle(String version) => t('updateTitle').replaceAll('{version}', version);
  String get updateBody => t('updateBody');
  String get updateAction => t('updateAction');
  String get updateLater => t('updateLater');
  String get updateCurrent => t('updateCurrent');
  String updateDownload(String version) => t('updateDownload').replaceAll('{version}', version);
  String get updateFailed => t('updateFailed');
  String get resetStats => t('resetStats');
  String get resetStatsTitle => t('resetStatsTitle');
  String get resetStatsBody => t('resetStatsBody');
  String get reset => t('reset');
  String get statsCleared => t('statsCleared');

  String get listening => t('listening');
  String get idleHint => t('idleHint');
  String every(int minutes) => t('every').replaceAll('{n}', '$minutes').replaceAll('{unit}', _unit(minutes));
  String listeningFor(int minutes) => t('listening').replaceAll('{n}', '$minutes').replaceAll('{unit}', _unit(minutes));
  String idleFor(int minutes) => t('idleHint').replaceAll('{n}', '$minutes').replaceAll('{unit}', _unit(minutes));
  String minutesLabel(int minutes) => t('minutesLabel').replaceAll('{n}', '$minutes');
  String _unit(int minutes) => minutes == 1 ? t('unitOne') : t('unitMany');
  String get stop => t('stop');
  String get stopClassification => t('stopClassification');
  String get startClassification => t('startClassification');
  String get onePass => t('onePass');
  String get refresh => t('refresh');
  String get howItDecides => t('howItDecides');
  String get fiveLooks => t('fiveLooks');
  String get stageThread => t('stageThread');
  String get stageThreadHint => t('stageThreadHint');
  String get stageSender => t('stageSender');
  String get stageSenderHint => t('stageSenderHint');
  String get stageDomain => t('stageDomain');
  String get stageDomainHint => t('stageDomainHint');
  String get stageMemory => t('stageMemory');
  String get stageMemoryHint => t('stageMemoryHint');
  String get stagePrior => t('stagePrior');
  String get stagePriorHint => t('stagePriorHint');
  String get youMove => t('youMove');
  String get numberThatCounts => t('numberThatCounts');
  String get correctionsEvery100 => t('correctionsEvery100');
  String get correctionsExplain => t('correctionsExplain');
  String get classified => t('classified');
  String get classifiedHint => t('classifiedHint');
  String get alreadyRight => t('alreadyRight');
  String get alreadyRightHint => t('alreadyRightHint');
  String get leftThere => t('leftThere');
  String get leftThereHint => t('leftThereHint');
  String get untouched => t('untouched');
  String get untouchedHint => t('untouchedHint');
  String get lastFolderUrgent => t('lastFolderUrgent');
  String get firstFolderUrgent => t('firstFolderUrgent');
  String get whereTheyGo => t('whereTheyGo');
  String get recentTitle => t('recentTitle');
  String get recentHint => t('recentHint');
  String get noneYet => t('noneYet');
  String get unknownSender => t('unknownSender');
  String get wonThread => t('wonThread');
  String get wonSender => t('wonSender');
  String get wonDomain => t('wonDomain');
  String get wonMemory => t('wonMemory');
  String get wonPrior => t('wonPrior');

  String get processing => t('processing');
  String get listeningBadge => t('listeningBadge');
  String get intervalScope => t('intervalScope');

  String get mailboxesTitle => t('mailboxesTitle');
  String get mailboxesSubtitle => t('mailboxesSubtitle');
  String get account => t('account');
  String get accountWorking => t('accountWorking');
  String get accountSave => t('accountSave');
  String get accountType => t('accountType');
  String get hostImap => t('hostImap');
  String get user => t('user');
  String get password => t('password');
  String get userHint => t('userHint');
  String get otherAddresses => t('otherAddresses');
  String get otherAddressesHint => t('otherAddressesHint');
  String get tryLogin => t('tryLogin');
  String get priority => t('priority');
  String get graphPriority => t('graphPriority');
  String get gmailPriority => t('gmailPriority');
  String get imapPriority => t('imapPriority');
  String get whereMailGoes => t('whereMailGoes');
  String get labelStays => t('labelStays');
  String get moveToFolder => t('moveToFolder');
  String get foldersOnly => t('foldersOnly');
  String get labelExplain => t('labelExplain');
  String get moveExplain => t('moveExplain');
  String get labelNames => t('labelNames');
  String get folderNames => t('folderNames');
  String get howMany => t('howMany');
  String get whichUrgent => t('whichUrgent');
  String get theFirst => t('theFirst');
  String get theLast => t('theLast');
  String get darkIsUrgent => t('darkIsUrgent');
  String get save => t('save');
  String get removeMailbox => t('removeMailbox');
  String get trained => t('trained');
  String get training => t('training');
  String get trainedBody => t('trainedBody');
  String get trainingBody => t('trainingBody');
  String get startTraining => t('startTraining');
  String get trainAgain => t('trainAgain');
  String get alerts => t('alerts');
  String get alertsBody => t('alertsBody');
  String get desktopNotifications => t('desktopNotifications');
  String get notificationsScope => t('notificationsScope');
  String get mostUrgent => t('mostUrgent');
  String get noPriorityOn => t('noPriorityOn');
  String get addMailbox => t('addMailbox');
  String get newMailbox => t('newMailbox');

  String get removeTitle => t('removeTitle');
  String get removeBody => t('removeBody');
  String get cancel => t('cancel');
  String get remove => t('remove');
  String get retrainTitle => t('retrainTitle');
  String get retrainBody => t('retrainBody');

  String get needHost => t('needHost');
  String get savedMailbox => t('savedMailbox');
  String get trainingDone => t('trainingDone');
  String get macDenied => t('macDenied');
  String get oauthSaved => t('oauthSaved');

  String get ready => t('ready');
  String get interrupted => t('interrupted');
  String get loginOk => t('loginOk');
  String get done => t('done');
  String get failed => t('failed');
  String get checking => t('checking');
  String get preparing => t('preparing');
  String get searchingUnread => t('searchingUnread');
  String get classifyingUnread => t('classifyingUnread');
  String get checkingMoves => t('checkingMoves');
  String get inProgress => t('inProgress');
  String get waitingBrowser => t('waitingBrowser');
  String get connectingGmail => t('connectingGmail');
  String get connectingMicrosoft => t('connectingMicrosoft');
  String get linked => t('linked');
  String get linkFailed => t('linkFailed');
  String get alertPrefix => t('alertPrefix');

  String get passwordRejected => t('passwordRejected');
  String get passwordMissing => t('passwordMissing');
  String get canLabel => t('canLabel');
  String get foldersOnlyProvider => t('foldersOnlyProvider');
  String get closingRead => t('closingRead');
  String get learningMoves => t('learningMoves');
  String get connectingMailbox => t('connectingMailbox');
  String get creatingFolders => t('creatingFolders');
  String get countingSent => t('countingSent');

  String get serviceTitle => t('serviceTitle');
  String get serviceSubtitle => t('serviceSubtitle');
  String get log => t('log');
  String get clear => t('clear');
  String get logEmpty => t('logEmpty');

  String get gmailOnce => t('gmailOnce');
  String get microsoftOnce => t('microsoftOnce');
  String get gmailSteps => t('gmailSteps');
  String get microsoftSteps => t('microsoftSteps');
  String get googleClientId => t('googleClientId');
  String get googleSecret => t('googleSecret');
  String get microsoftAppId => t('microsoftAppId');
  String get saveLink => t('saveLink');
  String get relink => t('relink');
  String get link => t('link');
  String get accountLinked => t('accountLinked');

  String get correctionsPer100Menu => t('correctionsPer100Menu');
  String get classificationOn => t('classificationOn');
  String get classificationPaused => t('classificationPaused');
  String get pause => t('pause');
  String get openNeura => t('openNeura');
  String get quit => t('quit');
  String get open => t('open');
}

const _it = {
  'navModel': 'Modello',
  'navMailboxes': 'Caselle',
  'navService': 'Servizio',
  'language': 'Lingua',
  'release': 'Release',
  'resetStats': 'Azzera statistiche',
  'resetStatsTitle': 'Azzerare le statistiche?',
  'resetStatsBody': 'I numeri di questa casella tornano a zero. Quello che NeuraEC ha già imparato resta.',
  'reset': 'Azzera',
  'statsCleared': 'Statistiche azzerate.',
  'listening': 'NeuraEC è in ascolto: ogni {n} {unit} classifica e impara dai tuoi spostamenti.',
  'idleHint': 'Avvia classificazione la ripete ogni {n} {unit}. Solo un passaggio ne fa uno.',
  'every': 'Ogni {n} {unit}',
  'minutesLabel': '{n} min',
  'unitOne': 'minuto',
  'unitMany': 'minuti',
  'intervalScope': 'Per tutte le caselle',
  'stop': 'Interrompi',
  'stopClassification': 'Ferma classificazione',
  'startClassification': 'Avvia classificazione',
  'onePass': 'Solo un passaggio',
  'refresh': 'Aggiorna',
  'howItDecides': 'Come decide',
  'fiveLooks': 'Cinque sguardi sulla stessa mail. Vince il più sicuro, non una media.',
  'stageThread': 'Thread',
  'stageThreadHint': 'Il filo già aperto',
  'stageSender': 'Mittente',
  'stageSenderHint': 'Dove finisce di solito',
  'stageDomain': 'Dominio',
  'stageDomainHint': 'Se il mittente è nuovo',
  'stageMemory': 'Memoria',
  'stageMemoryHint': 'Mail simili già viste',
  'stagePrior': 'Prior',
  'stagePriorHint': 'La regola a freddo',
  'youMove': 'NeuraEC sceglie la priorità. Tu sposti la mail, e la prossima volta lo sa già.',
  'numberThatCounts': 'Il numero che conta',
  'correctionsEvery100': 'correzioni ogni 100',
  'correctionsExplain': 'Quante mail, tra quelle su cui hai già agito, hai spostato in un’altra priorità. Deve scendere nelle prime settimane.',
  'classified': 'Classificate',
  'classifiedHint': 'Già messe in una cartella di priorità.',
  'alreadyRight': 'Nel posto giusto',
  'alreadyRightHint': 'Tra le mail su cui hai già agito.',
  'leftThere': 'Lasciate lì',
  'leftThereHint': 'Lette e non spostate. Si contano dalla notte dopo.',
  'untouched': 'Non toccate',
  'untouchedHint': 'Né lette né spostate. Non entrano nel conto.',
  'lastFolderUrgent': 'L’ultima cartella è la più urgente',
  'firstFolderUrgent': 'La prima cartella è la più urgente',
  'whereTheyGo': 'Dove le sta mettendo',
  'recentTitle': 'Ultime classificate',
  'recentHint': 'Le più recenti, già nella loro cartella.',
  'noneYet': 'Ancora nessuna.',
  'unknownSender': 'mittente sconosciuto',
  'wonThread': 'Ha vinto il thread',
  'wonSender': 'Ha vinto il mittente',
  'wonDomain': 'Ha vinto il dominio',
  'wonMemory': 'Ha vinto la memoria',
  'wonPrior': 'Ha vinto il prior',
  'processing': 'IN ELABORAZIONE',
  'listeningBadge': 'IN ASCOLTO',
  'mailboxesTitle': 'Caselle',
  'mailboxesSubtitle': 'Ogni account ha le sue cartelle. NeuraEC le classifica tutte.',
  'account': 'Account',
  'accountWorking': 'NeuraEC sta già lavorando su questo account.',
  'accountSave': 'Salva per farla entrare nella classificazione insieme alle altre.',
  'accountType': 'Tipo di account',
  'hostImap': 'Host IMAP',
  'user': 'Utente',
  'password': 'Password',
  'userHint': 'Si compila da solo dopo Collega. Puoi lasciarlo vuoto.',
  'otherAddresses': 'Altri indirizzi della stessa casella',
  'otherAddressesHint': 'Separati da virgola. Se lo lasci vuoto, uso l’utente.',
  'tryLogin': 'Prova accesso',
  'priority': 'Priorità',
  'graphPriority': 'Su Microsoft possono essere categorie di Outlook o cartelle.',
  'gmailPriority': 'Su Gmail sono etichette: la mail può restare in Arrivo o uscirne.',
  'imapPriority': 'Su IMAP il numero si aggiunge da solo, dentro INBOX.',
  'whereMailGoes': 'Dove finisce la mail classificata',
  'labelStays': 'Etichetta, resta in Arrivo',
  'moveToFolder': 'Sposta nella cartella',
  'foldersOnly': 'Questo provider ha solo cartelle: la mail viene spostata in quella della sua priorità.',
  'labelExplain': 'La leggi dove sei abituato; l’etichetta dice la priorità. Spostarla tra le etichette insegna al modello.',
  'moveExplain': 'Arrivo resta pulita; ogni priorità ha la sua cartella. Spostarla tra le cartelle insegna al modello.',
  'labelNames': 'Nome delle etichette',
  'folderNames': 'Nome delle cartelle',
  'howMany': 'Quante',
  'whichUrgent': 'Quale è la più urgente',
  'theFirst': 'La prima',
  'theLast': 'L’ultima',
  'darkIsUrgent': 'Quella scura è la più urgente.',
  'save': 'Salva',
  'removeMailbox': 'Togli questa casella',
  'trained': 'Addestrata',
  'training': 'Addestramento',
  'trainedBody': 'NeuraEC ha già imparato da questa casella. Rifarlo rilegge le inviate degli ultimi 90 giorni.',
  'trainingBody': 'Impara dalle mail inviate negli ultimi 90 giorni. Si fa una volta, prima di classificare.',
  'startTraining': 'Avvia addestramento',
  'trainAgain': 'Addestra di nuovo',
  'alerts': 'Avvisi',
  'alertsBody': 'Scegli per quali priorità di questa casella vuoi una notifica sul desktop.',
  'desktopNotifications': 'Notifiche sul desktop',
  'notificationsScope': 'Vale per tutte le caselle. Arrivano finché NeuraEC è aperta o ridotta nella barra.',
  'mostUrgent': 'La più urgente',
  'noPriorityOn': 'Nessuna priorità accesa: nessun avviso per questa casella.',
  'addMailbox': 'Aggiungi casella',
  'newMailbox': 'Nuova casella',
  'removeTitle': 'Togliere questa casella?',
  'removeBody': 'Non viene più classificata. Le mail già spostate restano nelle loro cartelle.',
  'cancel': 'Annulla',
  'remove': 'Togli',
  'retrainTitle': 'Addestrare di nuovo?',
  'retrainBody': 'NeuraEC ha già imparato da questa casella. Rifarlo rilegge le inviate degli ultimi 90 giorni. Non è necessario per classificare.',
  'needHost': 'Servono host e utente.',
  'savedMailbox': 'Casella salvata. La password non è nel file di configurazione.',
  'trainingDone': 'Addestramento fatto. Non serve rifarlo, se non cambi nome o numero.',
  'macDenied': 'Il Mac non ha concesso gli avvisi. Si riattivano da Impostazioni di Sistema, Notifiche, NeuraEC.',
  'notificationsActive': 'Gli avvisi sono attivi per {account}.',
  'oauthSaved': 'Collegamento salvato. I segreti non sono nella casella.',
  'ready': 'Pronto',
  'interrupted': 'Passaggio interrotto',
  'loginOk': 'Accesso riuscito',
  'done': 'Fatto',
  'failed': 'Operazione non riuscita',
  'checking': 'Verifico utente e password…',
  'preparing': 'Preparo la casella…',
  'searchingUnread': 'Cerco le mail non lette…',
  'classifyingUnread': 'Classifico le mail non lette…',
  'checkingMoves': 'Controllo cosa hai spostato…',
  'inProgress': 'In corso…',
  'waitingBrowser': 'In attesa del browser…',
  'connectingGmail': 'Collegamento Gmail',
  'connectingMicrosoft': 'Collegamento Microsoft',
  'linked': 'Collegato',
  'linkFailed': 'Collegamento non riuscito',
  'alertPrefix': 'Avviso',
  'passwordRejected': 'Password rifiutata',
  'passwordMissing': 'Manca la password',
  'canLabel': 'Il provider sa etichettare',
  'foldersOnlyProvider': 'Il provider ha solo cartelle',
  'closingRead': 'Chiudo le mail lette da più di 24 ore…',
  'learningMoves': 'Imparo dai tuoi spostamenti…',
  'connectingMailbox': 'Connessione alla casella…',
  'creatingFolders': 'Creo le cartelle di priorità…',
  'countingSent': 'Conto a chi hai scritto negli ultimi 90 giorni. Non classifico le inviate.',
  'serviceTitle': 'Servizio',
  'serviceSubtitle': 'Tutto quello che succede, dal primo passaggio all’ultimo.',
  'log': 'Registro',
  'clear': 'Pulisci',
  'logEmpty': 'Qui compare tutto: classificazione, spostamenti imparati, avvisi, collegamenti.',
  'gmailOnce': 'Collegamento Gmail, una volta sola',
  'microsoftOnce': 'Collegamento Microsoft, una volta sola',
  'gmailSteps': 'In Google Cloud Console crea un progetto, abilita Gmail API e crea una credenziale di tipo Applicazione desktop. Incolla qui ID e segreto. Nella schermata di consenso premi Pubblica app: non mandarla in verifica. Al primo accesso Google dice che l’app non è verificata: Avanzate, poi vai all’app. Così il collegamento non scade dopo 7 giorni. La verifica serve solo se l’app deve accettare chiunque, non per il tuo uso. Non lasciarla in Test: lì il token muore dopo una settimana.',
  'microsoftSteps': 'Nel portale Azure, Microsoft Entra ID, registra un’app per account personali e aziendali. È un client pubblico: niente segreto. Come reindirizzamento metti http://127.0.0.1:8766. Autorizzazioni delegate: Mail.ReadWrite, MailboxSettings.ReadWrite, offline_access, User.Read. Incolla qui l’ID applicazione. Se la casella è aziendale, un amministratore può dover approvare l’accesso.',
  'googleClientId': 'ID client Google',
  'googleSecret': 'Segreto client Google',
  'microsoftAppId': 'ID applicazione Microsoft',
  'saveLink': 'Salva collegamento',
  'relink': 'Ricollega',
  'link': 'Collega',
  'accountLinked': 'Account collegato. Il token non è nel file della casella.',
  'correctionsPer100Menu': 'Correzioni / 100',
  'classificationOn': 'Classificazione attiva',
  'classificationPaused': 'Classificazione in pausa',
  'pause': 'Metti in pausa',
  'openNeura': 'Apri NEURA',
  'quit': 'Esci',
  'open': 'Apri',
  'updateTitle': 'È disponibile NeuraEC {version}',
  'updateBody': 'Puoi scaricare la nuova versione. Il file si apre in Download e si installa come la prima volta.',
  'updateAction': 'Aggiorna',
  'updateLater': 'Più tardi',
  'updateCurrent': 'NeuraEC è aggiornato.',
  'updateDownload': 'Scarico NeuraEC {version}',
  'updateFailed': 'Non riesco a scaricare l’aggiornamento.',
  'mailOne': 'email',
  'mailMany': 'email',
};

const _en = {
  'navModel': 'Model',
  'navMailboxes': 'Mailboxes',
  'navService': 'Log',
  'language': 'Language',
  'release': 'Release',
  'resetStats': 'Reset statistics',
  'resetStatsTitle': 'Reset the statistics?',
  'resetStatsBody': 'The numbers for this mailbox go back to zero. What NeuraEC has already learned stays.',
  'reset': 'Reset',
  'statsCleared': 'Statistics reset.',
  'listening': 'NeuraEC is listening: every {n} {unit} it classifies and learns from your moves.',
  'idleHint': 'Start classification repeats it every {n} {unit}. One pass does it once.',
  'every': 'Every {n} {unit}',
  'minutesLabel': '{n} min',
  'unitOne': 'minute',
  'unitMany': 'minutes',
  'intervalScope': 'For every mailbox',
  'stop': 'Stop',
  'stopClassification': 'Stop classification',
  'startClassification': 'Start classification',
  'onePass': 'One pass only',
  'refresh': 'Refresh',
  'howItDecides': 'How it decides',
  'fiveLooks': 'Five looks at the same message. The most confident one wins, not an average.',
  'stageThread': 'Thread',
  'stageThreadHint': 'The thread already open',
  'stageSender': 'Sender',
  'stageSenderHint': 'Where they usually land',
  'stageDomain': 'Domain',
  'stageDomainHint': 'When the sender is new',
  'stageMemory': 'Memory',
  'stageMemoryHint': 'Similar mail already seen',
  'stagePrior': 'Prior',
  'stagePriorHint': 'The cold-start rule',
  'youMove': 'NeuraEC picks the priority. You move the message, and next time it already knows.',
  'numberThatCounts': 'The number that matters',
  'correctionsEvery100': 'corrections per 100',
  'correctionsExplain': 'Of the messages you already acted on, how many you moved to another priority. It should fall in the first weeks.',
  'classified': 'Classified',
  'classifiedHint': 'Already filed in a priority folder.',
  'alreadyRight': 'Already right',
  'alreadyRightHint': 'Among the messages you already acted on.',
  'leftThere': 'Left there',
  'leftThereHint': 'Read and not moved. Counted the night after.',
  'untouched': 'Untouched',
  'untouchedHint': 'Neither read nor moved. They stay out of the score.',
  'lastFolderUrgent': 'The last folder is the most urgent',
  'firstFolderUrgent': 'The first folder is the most urgent',
  'whereTheyGo': 'Where it is filing them',
  'recentTitle': 'Latest classified',
  'recentHint': 'The most recent, already in their folder.',
  'noneYet': 'None yet.',
  'unknownSender': 'unknown sender',
  'wonThread': 'The thread won',
  'wonSender': 'The sender won',
  'wonDomain': 'The domain won',
  'wonMemory': 'Memory won',
  'wonPrior': 'The prior won',
  'processing': 'WORKING',
  'listeningBadge': 'LISTENING',
  'mailboxesTitle': 'Mailboxes',
  'mailboxesSubtitle': 'Each account has its own folders. NeuraEC classifies all of them.',
  'account': 'Account',
  'accountWorking': 'NeuraEC is already working on this account.',
  'accountSave': 'Save it to include it in classification with the others.',
  'accountType': 'Account type',
  'hostImap': 'IMAP host',
  'user': 'Username',
  'password': 'Password',
  'userHint': 'Filled in after Connect. You can leave it empty.',
  'otherAddresses': 'Other addresses of the same mailbox',
  'otherAddressesHint': 'Separated by commas. If you leave it empty, the username is used.',
  'tryLogin': 'Test login',
  'priority': 'Priority',
  'graphPriority': 'On Microsoft these can be Outlook categories or folders.',
  'gmailPriority': 'On Gmail these are labels: the message can stay in the inbox or leave it.',
  'imapPriority': 'On IMAP the number is added for you, inside INBOX.',
  'whereMailGoes': 'Where a classified message goes',
  'labelStays': 'Label, stay in Inbox',
  'moveToFolder': 'Move into the folder',
  'foldersOnly': 'This provider only has folders: the message is moved into the one for its priority.',
  'labelExplain': 'You read it where you always do; the label says the priority. Moving it between labels teaches the model.',
  'moveExplain': 'The inbox stays clean; each priority has its folder. Moving it between folders teaches the model.',
  'labelNames': 'Label names',
  'folderNames': 'Folder names',
  'howMany': 'How many',
  'whichUrgent': 'Which one is most urgent',
  'theFirst': 'The first',
  'theLast': 'The last',
  'darkIsUrgent': 'The dark one is the most urgent.',
  'save': 'Save',
  'removeMailbox': 'Remove this mailbox',
  'trained': 'Trained',
  'training': 'Training',
  'trainedBody': 'NeuraEC has already learned from this mailbox. Doing it again rereads mail sent in the last 90 days.',
  'trainingBody': 'It learns from mail sent in the last 90 days. Once, before classifying.',
  'startTraining': 'Start training',
  'trainAgain': 'Train again',
  'alerts': 'Alerts',
  'alertsBody': 'Choose which priorities of this mailbox should raise a desktop notification.',
  'desktopNotifications': 'Desktop notifications',
  'notificationsScope': 'Applies to every mailbox. They arrive while NeuraEC is open or sitting in the menu bar.',
  'mostUrgent': 'Most urgent',
  'noPriorityOn': 'No priority is on: no alerts for this mailbox.',
  'addMailbox': 'Add mailbox',
  'newMailbox': 'New mailbox',
  'removeTitle': 'Remove this mailbox?',
  'removeBody': 'It will no longer be classified. Messages already moved stay in their folders.',
  'cancel': 'Cancel',
  'remove': 'Remove',
  'retrainTitle': 'Train again?',
  'retrainBody': 'NeuraEC has already learned from this mailbox. Doing it again rereads mail sent in the last 90 days. It is not required to classify.',
  'needHost': 'Host and username are required.',
  'savedMailbox': 'Mailbox saved. The password is not in the configuration file.',
  'trainingDone': 'Training done. No need to repeat it, unless you change the name or the number.',
  'macDenied': 'The Mac did not allow alerts. Turn them back on in System Settings, Notifications, NeuraEC.',
  'notificationsActive': 'Alerts are on for {account}.',
  'oauthSaved': 'Connection saved. The secrets are not in the mailbox file.',
  'ready': 'Ready',
  'interrupted': 'Pass interrupted',
  'loginOk': 'Signed in',
  'done': 'Done',
  'failed': 'Something went wrong',
  'checking': 'Checking username and password…',
  'preparing': 'Preparing the mailbox…',
  'searchingUnread': 'Looking for unread mail…',
  'classifyingUnread': 'Classifying unread mail…',
  'checkingMoves': 'Checking what you moved…',
  'inProgress': 'Working…',
  'waitingBrowser': 'Waiting for the browser…',
  'connectingGmail': 'Gmail connection',
  'connectingMicrosoft': 'Microsoft connection',
  'linked': 'Connected',
  'linkFailed': 'Connection failed',
  'alertPrefix': 'Alert',
  'passwordRejected': 'Password rejected',
  'passwordMissing': 'Password missing',
  'canLabel': 'This provider can label',
  'foldersOnlyProvider': 'This provider only has folders',
  'closingRead': 'Closing mail read more than 24 hours ago…',
  'learningMoves': 'Learning from your moves…',
  'connectingMailbox': 'Connecting to the mailbox…',
  'creatingFolders': 'Creating the priority folders…',
  'countingSent': 'Counting who you wrote to in the last 90 days. Sent mail is not classified.',
  'serviceTitle': 'Log',
  'serviceSubtitle': 'Everything that happens, from the first pass to the last.',
  'log': 'Log',
  'clear': 'Clear',
  'logEmpty': 'Everything shows up here: classification, moves learned, alerts, connections.',
  'gmailOnce': 'Gmail connection, once',
  'microsoftOnce': 'Microsoft connection, once',
  'gmailSteps': 'In Google Cloud Console create a project, enable the Gmail API and create a Desktop app credential. Paste the ID and secret here. On the consent screen press Publish app: do not send it for verification. The first time, Google says the app is not verified: Advanced, then continue to the app. The connection then does not expire after 7 days. Verification is only needed if the app must accept anyone, not for your own use. Do not leave it in Testing: the token dies after a week.',
  'microsoftSteps': 'In the Azure portal, Microsoft Entra ID, register an app for personal and work accounts. It is a public client: no secret. Set the redirect to http://127.0.0.1:8766. Delegated permissions: Mail.ReadWrite, MailboxSettings.ReadWrite, offline_access, User.Read. Paste the application ID here. For a work mailbox, an administrator may have to approve access.',
  'googleClientId': 'Google client ID',
  'googleSecret': 'Google client secret',
  'microsoftAppId': 'Microsoft application ID',
  'saveLink': 'Save connection',
  'relink': 'Reconnect',
  'link': 'Connect',
  'accountLinked': 'Account connected. The token is not in the mailbox file.',
  'correctionsPer100Menu': 'Corrections / 100',
  'classificationOn': 'Classification on',
  'classificationPaused': 'Classification paused',
  'pause': 'Pause',
  'openNeura': 'Open NEURA',
  'quit': 'Quit',
  'open': 'Open',
  'updateTitle': 'NeuraEC {version} is available',
  'updateBody': 'You can download the new version. The file opens in Downloads and installs the same way as the first time.',
  'updateAction': 'Update',
  'updateLater': 'Later',
  'updateCurrent': 'NeuraEC is up to date.',
  'updateDownload': 'Downloading NeuraEC {version}',
  'updateFailed': 'The update could not be downloaded.',
  'mailOne': 'email',
  'mailMany': 'emails',
};

const _fr = {
  'navModel': 'Modèle',
  'navMailboxes': 'Boîtes',
  'navService': 'Journal',
  'language': 'Langue',
  'release': 'Release',
  'resetStats': 'Remettre les statistiques à zéro',
  'resetStatsTitle': 'Remettre les statistiques à zéro ?',
  'resetStatsBody': 'Les chiffres de cette boîte reviennent à zéro. Ce que NeuraEC a déjà appris reste.',
  'reset': 'Remettre à zéro',
  'statsCleared': 'Statistiques remises à zéro.',
  'listening': 'NeuraEC est à l’écoute : toutes les {n} {unit}, il classe et apprend de vos déplacements.',
  'idleHint': 'Lancer le classement le répète toutes les {n} {unit}. Un seul passage n’en fait qu’un.',
  'every': 'Toutes les {n} {unit}',
  'minutesLabel': '{n} min',
  'unitOne': 'minute',
  'unitMany': 'minutes',
  'intervalScope': 'Pour toutes les boîtes',
  'stop': 'Interrompre',
  'stopClassification': 'Arrêter le classement',
  'startClassification': 'Lancer le classement',
  'onePass': 'Un seul passage',
  'refresh': 'Actualiser',
  'howItDecides': 'Comment il décide',
  'fiveLooks': 'Cinq regards sur le même message. Le plus sûr l’emporte, pas une moyenne.',
  'stageThread': 'Fil',
  'stageThreadHint': 'Le fil déjà ouvert',
  'stageSender': 'Expéditeur',
  'stageSenderHint': 'Là où il arrive d’habitude',
  'stageDomain': 'Domaine',
  'stageDomainHint': 'Si l’expéditeur est nouveau',
  'stageMemory': 'Mémoire',
  'stageMemoryHint': 'Des messages semblables déjà vus',
  'stagePrior': 'Prior',
  'stagePriorHint': 'La règle de départ',
  'youMove': 'NeuraEC choisit la priorité. Vous déplacez le message, et la prochaine fois il le sait déjà.',
  'numberThatCounts': 'Le chiffre qui compte',
  'correctionsEvery100': 'corrections pour 100',
  'correctionsExplain': 'Parmi les messages sur lesquels vous avez déjà agi, combien vous en avez déplacés vers une autre priorité. Il doit baisser les premières semaines.',
  'classified': 'Classés',
  'classifiedHint': 'Déjà rangés dans un dossier de priorité.',
  'alreadyRight': 'Au bon endroit',
  'alreadyRightHint': 'Parmi les messages sur lesquels vous avez déjà agi.',
  'leftThere': 'Laissés là',
  'leftThereHint': 'Lus et non déplacés. Comptés le lendemain soir.',
  'untouched': 'Non touchés',
  'untouchedHint': 'Ni lus ni déplacés. Ils n’entrent pas dans le compte.',
  'lastFolderUrgent': 'Le dernier dossier est le plus urgent',
  'firstFolderUrgent': 'Le premier dossier est le plus urgent',
  'whereTheyGo': 'Où il les range',
  'recentTitle': 'Derniers classés',
  'recentHint': 'Les plus récents, déjà dans leur dossier.',
  'noneYet': 'Aucun pour l’instant.',
  'unknownSender': 'expéditeur inconnu',
  'wonThread': 'Le fil l’a emporté',
  'wonSender': 'L’expéditeur l’a emporté',
  'wonDomain': 'Le domaine l’a emporté',
  'wonMemory': 'La mémoire l’a emporté',
  'wonPrior': 'Le prior l’a emporté',
  'processing': 'EN COURS',
  'listeningBadge': 'À L’ÉCOUTE',
  'mailboxesTitle': 'Boîtes',
  'mailboxesSubtitle': 'Chaque compte a ses dossiers. NeuraEC les classe tous.',
  'account': 'Compte',
  'accountWorking': 'NeuraEC travaille déjà sur ce compte.',
  'accountSave': 'Enregistrez-le pour l’ajouter au classement avec les autres.',
  'accountType': 'Type de compte',
  'hostImap': 'Hôte IMAP',
  'user': 'Utilisateur',
  'password': 'Mot de passe',
  'userHint': 'Rempli après Connecter. Vous pouvez le laisser vide.',
  'otherAddresses': 'Autres adresses de la même boîte',
  'otherAddressesHint': 'Séparées par une virgule. Si vous laissez vide, l’utilisateur est utilisé.',
  'tryLogin': 'Essayer l’accès',
  'priority': 'Priorité',
  'graphPriority': 'Chez Microsoft, ce peuvent être des catégories Outlook ou des dossiers.',
  'gmailPriority': 'Sur Gmail, ce sont des libellés : le message peut rester dans la boîte de réception ou en sortir.',
  'imapPriority': 'En IMAP, le numéro s’ajoute tout seul, dans INBOX.',
  'whereMailGoes': 'Où va le message classé',
  'labelStays': 'Libellé, reste dans la réception',
  'moveToFolder': 'Déplacer dans le dossier',
  'foldersOnly': 'Ce fournisseur n’a que des dossiers : le message est déplacé dans celui de sa priorité.',
  'labelExplain': 'Vous le lisez là où vous en avez l’habitude ; le libellé dit la priorité. Le déplacer d’un libellé à l’autre apprend au modèle.',
  'moveExplain': 'La réception reste nette ; chaque priorité a son dossier. Le déplacer d’un dossier à l’autre apprend au modèle.',
  'labelNames': 'Nom des libellés',
  'folderNames': 'Nom des dossiers',
  'howMany': 'Combien',
  'whichUrgent': 'Lequel est le plus urgent',
  'theFirst': 'Le premier',
  'theLast': 'Le dernier',
  'darkIsUrgent': 'Le plus sombre est le plus urgent.',
  'save': 'Enregistrer',
  'removeMailbox': 'Retirer cette boîte',
  'trained': 'Entraînée',
  'training': 'Entraînement',
  'trainedBody': 'NeuraEC a déjà appris de cette boîte. Le refaire relit les messages envoyés des 90 derniers jours.',
  'trainingBody': 'Il apprend des messages envoyés des 90 derniers jours. Une fois, avant de classer.',
  'startTraining': 'Lancer l’entraînement',
  'trainAgain': 'Entraîner à nouveau',
  'alerts': 'Alertes',
  'alertsBody': 'Choisissez pour quelles priorités de cette boîte vous voulez une notification sur le bureau.',
  'desktopNotifications': 'Notifications sur le bureau',
  'notificationsScope': 'Vaut pour toutes les boîtes. Elles arrivent tant que NeuraEC est ouvert ou réduit dans la barre.',
  'mostUrgent': 'La plus urgente',
  'noPriorityOn': 'Aucune priorité activée : aucune alerte pour cette boîte.',
  'addMailbox': 'Ajouter une boîte',
  'newMailbox': 'Nouvelle boîte',
  'removeTitle': 'Retirer cette boîte ?',
  'removeBody': 'Elle ne sera plus classée. Les messages déjà déplacés restent dans leurs dossiers.',
  'cancel': 'Annuler',
  'remove': 'Retirer',
  'retrainTitle': 'Entraîner à nouveau ?',
  'retrainBody': 'NeuraEC a déjà appris de cette boîte. Le refaire relit les messages envoyés des 90 derniers jours. Ce n’est pas nécessaire pour classer.',
  'needHost': 'L’hôte et l’utilisateur sont nécessaires.',
  'savedMailbox': 'Boîte enregistrée. Le mot de passe n’est pas dans le fichier de configuration.',
  'trainingDone': 'Entraînement terminé. Inutile de le refaire, sauf si vous changez le nom ou le nombre.',
  'macDenied': 'Le Mac n’a pas autorisé les alertes. On les réactive dans Réglages Système, Notifications, NeuraEC.',
  'notificationsActive': 'Les alertes sont actives pour {account}.',
  'oauthSaved': 'Connexion enregistrée. Les secrets ne sont pas dans la boîte.',
  'ready': 'Prêt',
  'interrupted': 'Passage interrompu',
  'loginOk': 'Accès réussi',
  'done': 'Terminé',
  'failed': 'L’opération a échoué',
  'checking': 'Vérification de l’utilisateur et du mot de passe…',
  'preparing': 'Préparation de la boîte…',
  'searchingUnread': 'Recherche des messages non lus…',
  'classifyingUnread': 'Classement des messages non lus…',
  'checkingMoves': 'Vérification de ce que vous avez déplacé…',
  'inProgress': 'En cours…',
  'waitingBrowser': 'En attente du navigateur…',
  'connectingGmail': 'Connexion Gmail',
  'connectingMicrosoft': 'Connexion Microsoft',
  'linked': 'Connecté',
  'linkFailed': 'Connexion échouée',
  'alertPrefix': 'Alerte',
  'passwordRejected': 'Mot de passe refusé',
  'passwordMissing': 'Mot de passe manquant',
  'canLabel': 'Ce fournisseur sait étiqueter',
  'foldersOnlyProvider': 'Ce fournisseur n’a que des dossiers',
  'closingRead': 'Clôture des messages lus depuis plus de 24 heures…',
  'learningMoves': 'J’apprends de vos déplacements…',
  'connectingMailbox': 'Connexion à la boîte…',
  'creatingFolders': 'Création des dossiers de priorité…',
  'countingSent': 'Je compte à qui vous avez écrit ces 90 derniers jours. Les messages envoyés ne sont pas classés.',
  'serviceTitle': 'Journal',
  'serviceSubtitle': 'Tout ce qui se passe, du premier passage au dernier.',
  'log': 'Journal',
  'clear': 'Effacer',
  'logEmpty': 'Tout apparaît ici : classement, déplacements appris, alertes, connexions.',
  'gmailOnce': 'Connexion Gmail, une seule fois',
  'microsoftOnce': 'Connexion Microsoft, une seule fois',
  'gmailSteps': 'Dans Google Cloud Console, créez un projet, activez l’API Gmail et créez un identifiant de type Application de bureau. Collez ici l’ID et le secret. Sur l’écran de consentement, appuyez sur Publier l’application : ne l’envoyez pas en vérification. Au premier accès, Google dit que l’application n’est pas vérifiée : Paramètres avancés, puis accéder à l’application. Ainsi la connexion n’expire pas après 7 jours. La vérification ne sert que si l’application doit accepter n’importe qui, pas pour votre usage. Ne la laissez pas en mode Test : le jeton y meurt après une semaine.',
  'microsoftSteps': 'Dans le portail Azure, Microsoft Entra ID, enregistrez une application pour les comptes personnels et professionnels. C’est un client public : pas de secret. Comme redirection, mettez http://127.0.0.1:8766. Autorisations déléguées : Mail.ReadWrite, MailboxSettings.ReadWrite, offline_access, User.Read. Collez ici l’ID d’application. Si la boîte est d’entreprise, un administrateur peut devoir approuver l’accès.',
  'googleClientId': 'ID client Google',
  'googleSecret': 'Secret client Google',
  'microsoftAppId': 'ID d’application Microsoft',
  'saveLink': 'Enregistrer la connexion',
  'relink': 'Reconnecter',
  'link': 'Connecter',
  'accountLinked': 'Compte connecté. Le jeton n’est pas dans le fichier de la boîte.',
  'correctionsPer100Menu': 'Corrections / 100',
  'classificationOn': 'Classement actif',
  'classificationPaused': 'Classement en pause',
  'pause': 'Mettre en pause',
  'openNeura': 'Ouvrir NEURA',
  'quit': 'Quitter',
  'open': 'Ouvrir',
  'updateTitle': 'NeuraEC {version} est disponible',
  'updateBody': 'Vous pouvez télécharger la nouvelle version. Le fichier s’ouvre dans Téléchargements et s’installe comme la première fois.',
  'updateAction': 'Mettre à jour',
  'updateLater': 'Plus tard',
  'updateCurrent': 'NeuraEC est à jour.',
  'updateDownload': 'Téléchargement de NeuraEC {version}',
  'updateFailed': 'Impossible de télécharger la mise à jour.',
  'mailOne': 'e-mail',
  'mailMany': 'e-mails',
};

const _de = {
  'navModel': 'Modell',
  'navMailboxes': 'Postfächer',
  'navService': 'Protokoll',
  'language': 'Sprache',
  'release': 'Release',
  'resetStats': 'Statistik zurücksetzen',
  'resetStatsTitle': 'Statistik zurücksetzen?',
  'resetStatsBody': 'Die Zahlen dieses Postfachs gehen auf null. Was NeuraEC schon gelernt hat, bleibt.',
  'reset': 'Zurücksetzen',
  'statsCleared': 'Statistik zurückgesetzt.',
  'listening': 'NeuraEC hört zu: alle {n} {unit} sortiert es und lernt aus deinen Verschiebungen.',
  'idleHint': 'Klassifizierung starten wiederholt sie alle {n} {unit}. Nur ein Durchgang macht genau einen.',
  'every': 'Alle {n} {unit}',
  'minutesLabel': '{n} Min.',
  'unitOne': 'Minute',
  'unitMany': 'Minuten',
  'intervalScope': 'Für alle Postfächer',
  'stop': 'Abbrechen',
  'stopClassification': 'Klassifizierung stoppen',
  'startClassification': 'Klassifizierung starten',
  'onePass': 'Nur ein Durchgang',
  'refresh': 'Aktualisieren',
  'howItDecides': 'Wie es entscheidet',
  'fiveLooks': 'Fünf Blicke auf dieselbe Nachricht. Der sicherste gewinnt, kein Mittelwert.',
  'stageThread': 'Thread',
  'stageThreadHint': 'Der schon offene Verlauf',
  'stageSender': 'Absender',
  'stageSenderHint': 'Wo er gewöhnlich landet',
  'stageDomain': 'Domain',
  'stageDomainHint': 'Wenn der Absender neu ist',
  'stageMemory': 'Gedächtnis',
  'stageMemoryHint': 'Ähnliche Nachrichten, schon gesehen',
  'stagePrior': 'Prior',
  'stagePriorHint': 'Die Regel am Anfang',
  'youMove': 'NeuraEC wählt die Priorität. Du verschiebst die Nachricht, und beim nächsten Mal weiß es das schon.',
  'numberThatCounts': 'Die Zahl, die zählt',
  'correctionsEvery100': 'Korrekturen je 100',
  'correctionsExplain': 'Wie viele Nachrichten du, von denen du schon etwas getan hast, in eine andere Priorität verschoben hast. Sie sollte in den ersten Wochen sinken.',
  'classified': 'Eingeordnet',
  'classifiedHint': 'Schon in einem Prioritätsordner.',
  'alreadyRight': 'Am richtigen Ort',
  'alreadyRightHint': 'Unter den Nachrichten, bei denen du schon gehandelt hast.',
  'leftThere': 'Liegen gelassen',
  'leftThereHint': 'Gelesen und nicht verschoben. Gezählt in der Nacht danach.',
  'untouched': 'Nicht angefasst',
  'untouchedHint': 'Weder gelesen noch verschoben. Sie zählen nicht mit.',
  'lastFolderUrgent': 'Der letzte Ordner ist der dringendste',
  'firstFolderUrgent': 'Der erste Ordner ist der dringendste',
  'whereTheyGo': 'Wohin es sie legt',
  'recentTitle': 'Zuletzt eingeordnet',
  'recentHint': 'Die neuesten, schon in ihrem Ordner.',
  'noneYet': 'Noch keine.',
  'unknownSender': 'unbekannter Absender',
  'wonThread': 'Der Thread hat gewonnen',
  'wonSender': 'Der Absender hat gewonnen',
  'wonDomain': 'Die Domain hat gewonnen',
  'wonMemory': 'Das Gedächtnis hat gewonnen',
  'wonPrior': 'Der Prior hat gewonnen',
  'processing': 'IN ARBEIT',
  'listeningBadge': 'HÖRT ZU',
  'mailboxesTitle': 'Postfächer',
  'mailboxesSubtitle': 'Jedes Konto hat seine Ordner. NeuraEC sortiert sie alle.',
  'account': 'Konto',
  'accountWorking': 'NeuraEC arbeitet schon an diesem Konto.',
  'accountSave': 'Speichern, damit es mit den anderen klassifiziert wird.',
  'accountType': 'Kontotyp',
  'hostImap': 'IMAP-Host',
  'user': 'Benutzer',
  'password': 'Passwort',
  'userHint': 'Wird nach Verbinden ausgefüllt. Kann leer bleiben.',
  'otherAddresses': 'Weitere Adressen desselben Postfachs',
  'otherAddressesHint': 'Durch Komma getrennt. Leer lassen, dann gilt der Benutzer.',
  'tryLogin': 'Zugang prüfen',
  'priority': 'Priorität',
  'graphPriority': 'Bei Microsoft können das Outlook-Kategorien oder Ordner sein.',
  'gmailPriority': 'Bei Gmail sind es Labels: die Nachricht kann im Posteingang bleiben oder ihn verlassen.',
  'imapPriority': 'Bei IMAP kommt die Zahl von selbst dazu, in INBOX.',
  'whereMailGoes': 'Wohin die eingeordnete Nachricht geht',
  'labelStays': 'Label, bleibt im Posteingang',
  'moveToFolder': 'In den Ordner verschieben',
  'foldersOnly': 'Dieser Anbieter hat nur Ordner: die Nachricht wird in den ihrer Priorität verschoben.',
  'labelExplain': 'Du liest sie, wo du es gewohnt bist; das Label sagt die Priorität. Sie zwischen Labels zu verschieben bringt dem Modell etwas bei.',
  'moveExplain': 'Der Posteingang bleibt leer; jede Priorität hat ihren Ordner. Sie zwischen Ordnern zu verschieben bringt dem Modell etwas bei.',
  'labelNames': 'Name der Labels',
  'folderNames': 'Name der Ordner',
  'howMany': 'Wie viele',
  'whichUrgent': 'Welche ist am dringendsten',
  'theFirst': 'Die erste',
  'theLast': 'Die letzte',
  'darkIsUrgent': 'Die dunkle ist die dringendste.',
  'save': 'Speichern',
  'removeMailbox': 'Dieses Postfach entfernen',
  'trained': 'Trainiert',
  'training': 'Training',
  'trainedBody': 'NeuraEC hat aus diesem Postfach schon gelernt. Nochmal liest die gesendeten Nachrichten der letzten 90 Tage neu.',
  'trainingBody': 'Es lernt aus den gesendeten Nachrichten der letzten 90 Tage. Einmal, vor dem Klassifizieren.',
  'startTraining': 'Training starten',
  'trainAgain': 'Erneut trainieren',
  'alerts': 'Hinweise',
  'alertsBody': 'Wähle, für welche Prioritäten dieses Postfachs du eine Benachrichtigung auf dem Schreibtisch willst.',
  'desktopNotifications': 'Benachrichtigungen auf dem Schreibtisch',
  'notificationsScope': 'Gilt für alle Postfächer. Sie kommen, solange NeuraEC offen oder in der Leiste ist.',
  'mostUrgent': 'Am dringendsten',
  'noPriorityOn': 'Keine Priorität an: keine Hinweise für dieses Postfach.',
  'addMailbox': 'Postfach hinzufügen',
  'newMailbox': 'Neues Postfach',
  'removeTitle': 'Dieses Postfach entfernen?',
  'removeBody': 'Es wird nicht mehr klassifiziert. Schon verschobene Nachrichten bleiben in ihren Ordnern.',
  'cancel': 'Abbrechen',
  'remove': 'Entfernen',
  'retrainTitle': 'Erneut trainieren?',
  'retrainBody': 'NeuraEC hat aus diesem Postfach schon gelernt. Nochmal liest die gesendeten Nachrichten der letzten 90 Tage neu. Zum Klassifizieren ist das nicht nötig.',
  'needHost': 'Host und Benutzer werden gebraucht.',
  'savedMailbox': 'Postfach gespeichert. Das Passwort steht nicht in der Konfigurationsdatei.',
  'trainingDone': 'Training fertig. Nicht wiederholen, außer du änderst Name oder Anzahl.',
  'macDenied': 'Der Mac hat die Hinweise nicht erlaubt. Wieder einschalten unter Systemeinstellungen, Mitteilungen, NeuraEC.',
  'notificationsActive': 'Hinweise sind an für {account}.',
  'oauthSaved': 'Verbindung gespeichert. Die Geheimnisse stehen nicht im Postfach.',
  'ready': 'Bereit',
  'interrupted': 'Durchgang abgebrochen',
  'loginOk': 'Angemeldet',
  'done': 'Fertig',
  'failed': 'Vorgang fehlgeschlagen',
  'checking': 'Benutzer und Passwort werden geprüft…',
  'preparing': 'Postfach wird vorbereitet…',
  'searchingUnread': 'Ungelesene Nachrichten werden gesucht…',
  'classifyingUnread': 'Ungelesene Nachrichten werden eingeordnet…',
  'checkingMoves': 'Es wird geprüft, was du verschoben hast…',
  'inProgress': 'Läuft…',
  'waitingBrowser': 'Warten auf den Browser…',
  'connectingGmail': 'Gmail-Verbindung',
  'connectingMicrosoft': 'Microsoft-Verbindung',
  'linked': 'Verbunden',
  'linkFailed': 'Verbindung fehlgeschlagen',
  'alertPrefix': 'Hinweis',
  'passwordRejected': 'Passwort abgelehnt',
  'passwordMissing': 'Passwort fehlt',
  'canLabel': 'Dieser Anbieter kann labeln',
  'foldersOnlyProvider': 'Dieser Anbieter hat nur Ordner',
  'closingRead': 'Nachrichten werden geschlossen, die seit über 24 Stunden gelesen sind…',
  'learningMoves': 'Ich lerne aus deinen Verschiebungen…',
  'connectingMailbox': 'Verbindung zum Postfach…',
  'creatingFolders': 'Prioritätsordner werden angelegt…',
  'countingSent': 'Ich zähle, wem du in den letzten 90 Tagen geschrieben hast. Gesendete Nachrichten werden nicht eingeordnet.',
  'serviceTitle': 'Protokoll',
  'serviceSubtitle': 'Alles, was passiert, vom ersten Durchgang bis zum letzten.',
  'log': 'Protokoll',
  'clear': 'Leeren',
  'logEmpty': 'Hier erscheint alles: Klassifizierung, gelernte Verschiebungen, Hinweise, Verbindungen.',
  'gmailOnce': 'Gmail-Verbindung, einmal',
  'microsoftOnce': 'Microsoft-Verbindung, einmal',
  'gmailSteps': 'In der Google Cloud Console ein Projekt anlegen, die Gmail-API aktivieren und Anmeldedaten vom Typ Desktopanwendung erstellen. ID und Geheimnis hier einfügen. Auf dem Einwilligungsbildschirm App veröffentlichen drücken: nicht zur Prüfung schicken. Beim ersten Zugriff sagt Google, die App sei nicht geprüft: Erweitert, dann zur App. So läuft die Verbindung nicht nach 7 Tagen ab. Die Prüfung braucht es nur, wenn die App jeden annehmen soll, nicht für deinen eigenen Gebrauch. Nicht im Test lassen: dort stirbt das Token nach einer Woche.',
  'microsoftSteps': 'Im Azure-Portal, Microsoft Entra ID, eine App für persönliche und Geschäftskonten registrieren. Es ist ein öffentlicher Client: kein Geheimnis. Als Umleitung http://127.0.0.1:8766 eintragen. Delegierte Berechtigungen: Mail.ReadWrite, MailboxSettings.ReadWrite, offline_access, User.Read. Die Anwendungs-ID hier einfügen. Bei einem Firmenpostfach muss ein Administrator den Zugriff vielleicht genehmigen.',
  'googleClientId': 'Google-Client-ID',
  'googleSecret': 'Google-Clientgeheimnis',
  'microsoftAppId': 'Microsoft-Anwendungs-ID',
  'saveLink': 'Verbindung speichern',
  'relink': 'Neu verbinden',
  'link': 'Verbinden',
  'accountLinked': 'Konto verbunden. Das Token steht nicht in der Postfachdatei.',
  'correctionsPer100Menu': 'Korrekturen / 100',
  'classificationOn': 'Klassifizierung aktiv',
  'classificationPaused': 'Klassifizierung pausiert',
  'pause': 'Pausieren',
  'openNeura': 'NEURA öffnen',
  'quit': 'Beenden',
  'open': 'Öffnen',
  'updateTitle': 'NeuraEC {version} ist verfügbar',
  'updateBody': 'Du kannst die neue Version laden. Die Datei öffnet sich in Downloads und wird wie beim ersten Mal installiert.',
  'updateAction': 'Aktualisieren',
  'updateLater': 'Später',
  'updateCurrent': 'NeuraEC ist aktuell.',
  'updateDownload': 'NeuraEC {version} wird geladen',
  'updateFailed': 'Die Aktualisierung konnte nicht geladen werden.',
  'mailOne': 'E-Mail',
  'mailMany': 'E-Mails',
};

const _es = {
  'navModel': 'Modelo',
  'navMailboxes': 'Buzones',
  'navService': 'Registro',
  'language': 'Idioma',
  'release': 'Release',
  'resetStats': 'Poner las estadísticas a cero',
  'resetStatsTitle': '¿Poner las estadísticas a cero?',
  'resetStatsBody': 'Los números de este buzón vuelven a cero. Lo que NeuraEC ya aprendió se queda.',
  'reset': 'Poner a cero',
  'statsCleared': 'Estadísticas a cero.',
  'listening': 'NeuraEC está escuchando: cada {n} {unit} clasifica y aprende de tus movimientos.',
  'idleHint': 'Iniciar clasificación lo repite cada {n} {unit}. Solo un paso hace uno.',
  'every': 'Cada {n} {unit}',
  'minutesLabel': '{n} min',
  'unitOne': 'minuto',
  'unitMany': 'minutos',
  'intervalScope': 'Para todos los buzones',
  'stop': 'Interrumpir',
  'stopClassification': 'Detener clasificación',
  'startClassification': 'Iniciar clasificación',
  'onePass': 'Solo un paso',
  'refresh': 'Actualizar',
  'howItDecides': 'Cómo decide',
  'fiveLooks': 'Cinco miradas al mismo mensaje. Gana el más seguro, no una media.',
  'stageThread': 'Hilo',
  'stageThreadHint': 'El hilo ya abierto',
  'stageSender': 'Remitente',
  'stageSenderHint': 'Dónde suele acabar',
  'stageDomain': 'Dominio',
  'stageDomainHint': 'Si el remitente es nuevo',
  'stageMemory': 'Memoria',
  'stageMemoryHint': 'Correos parecidos ya vistos',
  'stagePrior': 'Prior',
  'stagePriorHint': 'La regla de partida',
  'youMove': 'NeuraEC elige la prioridad. Tú mueves el mensaje, y la próxima vez ya lo sabe.',
  'numberThatCounts': 'El número que importa',
  'correctionsEvery100': 'correcciones cada 100',
  'correctionsExplain': 'De los mensajes sobre los que ya actuaste, cuántos moviste a otra prioridad. Debe bajar en las primeras semanas.',
  'classified': 'Clasificados',
  'classifiedHint': 'Ya colocados en una carpeta de prioridad.',
  'alreadyRight': 'En su sitio',
  'alreadyRightHint': 'Entre los mensajes sobre los que ya actuaste.',
  'leftThere': 'Dejados ahí',
  'leftThereHint': 'Leídos y no movidos. Se cuentan la noche siguiente.',
  'untouched': 'Sin tocar',
  'untouchedHint': 'Ni leídos ni movidos. No entran en la cuenta.',
  'lastFolderUrgent': 'La última carpeta es la más urgente',
  'firstFolderUrgent': 'La primera carpeta es la más urgente',
  'whereTheyGo': 'Dónde los está poniendo',
  'recentTitle': 'Últimos clasificados',
  'recentHint': 'Los más recientes, ya en su carpeta.',
  'noneYet': 'Todavía ninguno.',
  'unknownSender': 'remitente desconocido',
  'wonThread': 'Ganó el hilo',
  'wonSender': 'Ganó el remitente',
  'wonDomain': 'Ganó el dominio',
  'wonMemory': 'Ganó la memoria',
  'wonPrior': 'Ganó el prior',
  'processing': 'EN CURSO',
  'listeningBadge': 'A LA ESCUCHA',
  'mailboxesTitle': 'Buzones',
  'mailboxesSubtitle': 'Cada cuenta tiene sus carpetas. NeuraEC las clasifica todas.',
  'account': 'Cuenta',
  'accountWorking': 'NeuraEC ya está trabajando en esta cuenta.',
  'accountSave': 'Guárdala para que entre en la clasificación junto con las demás.',
  'accountType': 'Tipo de cuenta',
  'hostImap': 'Host IMAP',
  'user': 'Usuario',
  'password': 'Contraseña',
  'userHint': 'Se rellena solo después de Conectar. Puedes dejarlo vacío.',
  'otherAddresses': 'Otras direcciones del mismo buzón',
  'otherAddressesHint': 'Separadas por comas. Si lo dejas vacío, uso el usuario.',
  'tryLogin': 'Probar acceso',
  'priority': 'Prioridad',
  'graphPriority': 'En Microsoft pueden ser categorías de Outlook o carpetas.',
  'gmailPriority': 'En Gmail son etiquetas: el mensaje puede quedarse en Recibidos o salir.',
  'imapPriority': 'En IMAP el número se añade solo, dentro de INBOX.',
  'whereMailGoes': 'Dónde acaba el mensaje clasificado',
  'labelStays': 'Etiqueta, se queda en Recibidos',
  'moveToFolder': 'Mover a la carpeta',
  'foldersOnly': 'Este proveedor solo tiene carpetas: el mensaje se mueve a la de su prioridad.',
  'labelExplain': 'Lo lees donde estás acostumbrado; la etiqueta dice la prioridad. Moverlo entre etiquetas enseña al modelo.',
  'moveExplain': 'Recibidos queda limpio; cada prioridad tiene su carpeta. Moverlo entre carpetas enseña al modelo.',
  'labelNames': 'Nombre de las etiquetas',
  'folderNames': 'Nombre de las carpetas',
  'howMany': 'Cuántas',
  'whichUrgent': 'Cuál es la más urgente',
  'theFirst': 'La primera',
  'theLast': 'La última',
  'darkIsUrgent': 'La oscura es la más urgente.',
  'save': 'Guardar',
  'removeMailbox': 'Quitar este buzón',
  'trained': 'Entrenado',
  'training': 'Entrenamiento',
  'trainedBody': 'NeuraEC ya aprendió de este buzón. Repetirlo vuelve a leer los enviados de los últimos 90 días.',
  'trainingBody': 'Aprende de los mensajes enviados en los últimos 90 días. Se hace una vez, antes de clasificar.',
  'startTraining': 'Iniciar entrenamiento',
  'trainAgain': 'Entrenar de nuevo',
  'alerts': 'Avisos',
  'alertsBody': 'Elige para qué prioridades de este buzón quieres una notificación en el escritorio.',
  'desktopNotifications': 'Notificaciones en el escritorio',
  'notificationsScope': 'Vale para todos los buzones. Llegan mientras NeuraEC está abierto o reducido en la barra.',
  'mostUrgent': 'La más urgente',
  'noPriorityOn': 'Ninguna prioridad activa: ningún aviso para este buzón.',
  'addMailbox': 'Añadir buzón',
  'newMailbox': 'Buzón nuevo',
  'removeTitle': '¿Quitar este buzón?',
  'removeBody': 'Deja de clasificarse. Los mensajes ya movidos se quedan en sus carpetas.',
  'cancel': 'Cancelar',
  'remove': 'Quitar',
  'retrainTitle': '¿Entrenar de nuevo?',
  'retrainBody': 'NeuraEC ya aprendió de este buzón. Repetirlo vuelve a leer los enviados de los últimos 90 días. No hace falta para clasificar.',
  'needHost': 'Hacen falta el host y el usuario.',
  'savedMailbox': 'Buzón guardado. La contraseña no está en el archivo de configuración.',
  'trainingDone': 'Entrenamiento hecho. No hace falta repetirlo, salvo que cambies el nombre o el número.',
  'macDenied': 'El Mac no concedió los avisos. Se reactivan en Ajustes del Sistema, Notificaciones, NeuraEC.',
  'notificationsActive': 'Los avisos están activos para {account}.',
  'oauthSaved': 'Conexión guardada. Los secretos no están en el buzón.',
  'ready': 'Listo',
  'interrupted': 'Paso interrumpido',
  'loginOk': 'Acceso correcto',
  'done': 'Hecho',
  'failed': 'La operación no salió',
  'checking': 'Compruebo usuario y contraseña…',
  'preparing': 'Preparo el buzón…',
  'searchingUnread': 'Busco los mensajes no leídos…',
  'classifyingUnread': 'Clasifico los mensajes no leídos…',
  'checkingMoves': 'Compruebo lo que has movido…',
  'inProgress': 'En curso…',
  'waitingBrowser': 'Esperando al navegador…',
  'connectingGmail': 'Conexión con Gmail',
  'connectingMicrosoft': 'Conexión con Microsoft',
  'linked': 'Conectado',
  'linkFailed': 'Conexión fallida',
  'alertPrefix': 'Aviso',
  'passwordRejected': 'Contraseña rechazada',
  'passwordMissing': 'Falta la contraseña',
  'canLabel': 'El proveedor sabe etiquetar',
  'foldersOnlyProvider': 'El proveedor solo tiene carpetas',
  'closingRead': 'Cierro los mensajes leídos hace más de 24 horas…',
  'learningMoves': 'Aprendo de tus movimientos…',
  'connectingMailbox': 'Conexión con el buzón…',
  'creatingFolders': 'Creo las carpetas de prioridad…',
  'countingSent': 'Cuento a quién escribiste en los últimos 90 días. No clasifico los enviados.',
  'serviceTitle': 'Registro',
  'serviceSubtitle': 'Todo lo que ocurre, del primer paso al último.',
  'log': 'Registro',
  'clear': 'Limpiar',
  'logEmpty': 'Aquí aparece todo: clasificación, movimientos aprendidos, avisos, conexiones.',
  'gmailOnce': 'Conexión con Gmail, una sola vez',
  'microsoftOnce': 'Conexión con Microsoft, una sola vez',
  'gmailSteps': 'En Google Cloud Console crea un proyecto, activa la API de Gmail y crea una credencial de tipo Aplicación de escritorio. Pega aquí el ID y el secreto. En la pantalla de consentimiento pulsa Publicar aplicación: no la mandes a verificación. En el primer acceso Google dice que la aplicación no está verificada: Configuración avanzada y luego ir a la aplicación. Así la conexión no caduca a los 7 días. La verificación solo hace falta si la aplicación debe aceptar a cualquiera, no para tu uso. No la dejes en Prueba: ahí el token muere a la semana.',
  'microsoftSteps': 'En el portal de Azure, Microsoft Entra ID, registra una aplicación para cuentas personales y de empresa. Es un cliente público: sin secreto. Como redirección pon http://127.0.0.1:8766. Permisos delegados: Mail.ReadWrite, MailboxSettings.ReadWrite, offline_access, User.Read. Pega aquí el ID de aplicación. Si el buzón es de empresa, un administrador puede tener que aprobar el acceso.',
  'googleClientId': 'ID de cliente de Google',
  'googleSecret': 'Secreto de cliente de Google',
  'microsoftAppId': 'ID de aplicación de Microsoft',
  'saveLink': 'Guardar conexión',
  'relink': 'Reconectar',
  'link': 'Conectar',
  'accountLinked': 'Cuenta conectada. El token no está en el archivo del buzón.',
  'correctionsPer100Menu': 'Correcciones / 100',
  'classificationOn': 'Clasificación activa',
  'classificationPaused': 'Clasificación en pausa',
  'pause': 'Pausar',
  'openNeura': 'Abrir NEURA',
  'quit': 'Salir',
  'open': 'Abrir',
  'updateTitle': 'NeuraEC {version} está disponible',
  'updateBody': 'Puedes descargar la nueva versión. El archivo se abre en Descargas y se instala como la primera vez.',
  'updateAction': 'Actualizar',
  'updateLater': 'Más tarde',
  'updateCurrent': 'NeuraEC está actualizado.',
  'updateDownload': 'Descargando NeuraEC {version}',
  'updateFailed': 'No se puede descargar la actualización.',
  'mailOne': 'correo',
  'mailMany': 'correos',
};

const _catalogs = {
  'it': _it,
  'en': _en,
  'fr': _fr,
  'de': _de,
  'es': _es,
};
