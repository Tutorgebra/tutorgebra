// UI translations (English / Spanish). The page always starts in English; the choice is not persisted.
// Keep the import URL identical everywhere ('./i18n.js?v=N' / '../i18n.js?v=N') so every module shares one `lang`.
const { ref } = window.Vue;

export const LANGS = ['en', 'es'];
export const lang = ref('en');

const messages = {
    en: {
        'header.github': 'View source on GitHub',
        'header.apiKey': 'API Key',
        'header.theme': 'Toggle dark mode',
        'header.language': 'Language',
        'header.subtitle': 'Your automated interactive geometry tutor.',

        'prompt.label': 'What do you want to calculate or draw?',
        'prompt.placeholder': 'Ex: Draw a right triangle and its circumscribed circle.',
        'prompt.overLimit': 'You have exceeded the maximum limit of {n} characters. Please shorten your text to continue.',
        'image.attach': 'Attach image (optional)',
        'image.remove': 'Remove image',

        'voice.label': 'Teacher Voice',
        'voice.basic': 'Basic Voices (gTTS)',
        'voice.more': 'More Voices (edgeTTS)',
        'voice.auto': 'Auto-detect Language (AI)',
        'voice.spanishFemale': 'Spanish (Female only)',
        'voice.englishFemale': 'English (Female only)',
        'voice.spanish': 'Spanish',
        'voice.english': 'English',
        'voice.male': 'Male',
        'voice.female': 'Female',

        'model.label': 'AI Model',
        'model.auto': 'Auto (detects formula or reasoning)',
        'explain.label': 'Explain more',
        'explain.hint': 'Each step explains what is done, why, and what the result means. The lesson will be longer and take a little more time.',
        'model.autoHint': 'Formula exercises are solved with GPT-4o. Reasoning exercises (line balancing, optimization, scheduling...) go straight to Claude Sonnet 5.5 and may take up to a minute because of their complexity.',
        'difficulty.formula': 'Formula',
        'difficulty.reasoning': 'Reasoning',
        'difficulty.manual': 'Manual',
        'progress.reasoning': 'Reasoning exercise: it is solved with Claude Sonnet 5.5 and may take up to a minute...',
        'model.advanced': 'Advanced Math & Vision',
        'model.basic': 'Basic Math',
        'model.badge': 'Model',
        'lesson.checksFailed': "This lesson's own checks found a condition its solution does not meet, so its result may be wrong. Review it before trusting it.",
        'provider.fatal': 'The lesson could not be generated: {reason}.',
        'provider.warning': 'The AI model provider had problems while generating this lesson: {reasons}.',
        'provider.reason.credits': 'the provider account (OpenRouter) does not have enough credit',
        'provider.reason.rate_limit': 'the provider is limiting requests, wait a moment and try again',
        'provider.reason.timeout': 'the provider took too long to answer',
        'provider.reason.unavailable': 'the model provider is not available right now',
        'provider.reason.moderation': "the provider rejected the request with its content filters",
        'provider.reason.auth': 'the API key is not valid',
        'provider.reason.truncated': "the model's answer was cut off by its length limit",
        'provider.reason.empty': 'the model returned an empty answer',
        'provider.reason.review_failed': 'the lesson could not be verified by the reviewer',
        'provider.reason.provider': 'the model provider returned an error',

        'generate.idle': 'Generate Lesson',
        'generate.busy': 'Generating lesson...',

        'player.title': 'Player Controls',
        'player.restart': 'Restart',
        'player.next': 'Next Step',
        'download.button': 'Download lesson',
        'download.notReady': 'Finish the lesson to download it.',
        'download.failed': 'Could not create the lesson file. Please try again.',

        // Texts of the downloaded lesson (static/lesson_export.js)
        'export.fileFallback': 'lesson',
        'export.photoTitle': 'Exercise from a photo',
        'export.generated': 'Generated on {date}',
        'export.model': 'Model: {model}',
        'export.exercise': 'Exercise',
        'export.photoAlt': 'Photo of the exercise',
        'export.board': 'GeoGebra board',
        'export.loading': 'Loading GeoGebra...',
        'export.offline': 'GeoGebra could not load: it needs an internet connection. This is the image of the final board.',
        'export.final': 'Show final result',
        'export.finalStatus': 'Board with the final result',
        'export.stepStatus': 'Board at step {n} of {total}',
        'export.graphAlt': 'Final board of the lesson',
        'export.ggb': 'Download .ggb file',
        'export.ggbHint': 'Opens in the GeoGebra app or at geogebra.org/classic',
        'export.print': 'Print or save as PDF',
        'export.steps': 'Step by step',
        'export.boardHint': 'Use "Show on the board" on any step to see the board at that point of the lesson.',
        'export.explanation': 'Explanation',
        'export.show': 'Show on the board',
        'export.listen': '▶ Listen',
        'export.stop': '■ Stop',
        'export.footer': 'Lesson generated by TutorGebra',

        'board.title': 'Interactive Board',
        'board.fullscreen': 'Fullscreen',
        'board.empty': 'Enter your query to load the engine.',

        'footer.createdBy': 'Created by',
        'footer.license': 'Non-profit, MIT License.',

        'select.placeholder': 'Select...',
        'examples.title': 'Ideas / Examples',
        'examples.use': 'Click to use this example',

        'tips.title': 'Did you know?',
        'tips.1': 'The gpt-4o-mini model can hallucinate with complex problems. We recommend using gpt-4o.',
        'tips.2': 'Star this repository on GitHub! ⭐',
        'tips.3': "See an issue / hallucination? Open an issue, we'll look into it!",
        'tips.4': 'Have an OpenRouter API key? You can use it!',
        'tips.5': 'Open a discussion on GitHub to suggest changes or new features!',
        'tips.6': 'We are looking for expert help to improve the application! Contributions are welcome.',

        'modal.title': 'OpenRouter API Key',
        'modal.optional': '(Optional)',
        'modal.close': 'Close',
        'modal.placeholder': "Leave blank to use Server's free key",
        'modal.serverNote': 'Uses server key by default. Enter your own for private quotas.',
        'modal.clear': 'Clear key',
        'modal.intro': 'TutorGebra needs a "brain" to read your exercises and convert them into geometric code. We use <strong>OpenRouter</strong> to route your requests to the best free AI models available (like Gemini). If the server key is exhausted, you can use your own personal key.',
        'modal.secure': '<strong>100% Secure:</strong> Your API key acts as a direct bridge between you and OpenRouter. We never log, collect, or store your key on our servers.',
        'modal.stepsTitle': "Steps to get your key (It's free!):",
        'modal.step1': 'Go to <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 hover:underline font-semibold">OpenRouter.ai</a>.',
        'modal.step2': 'Log in with your Google or GitHub account.',
        'modal.step3': 'Click the <strong>"Create Key"</strong> button.',
        'modal.step4': 'Copy the generated code and paste it into TutorGebra.',
        'modal.done': 'Done',

        'progress.starting': 'Starting...',
        'progress.thinking': 'Thinking about the mathematical solution...',
        'progress.evaluating': 'Checking the values on the board...',
        'progress.generated': 'Lesson generated ({n} steps). Synthesizing teacher voice...',
        'progress.audioStep': 'Synthesizing audio step {a}/{b}...',

        'error.notImage': 'The selected file is not an image.',
        'error.imageTooLarge': 'The image is too large, even after compressing it.',
        'error.imageUnreadable': 'Could not read the image.',
        'error.server': 'Server error',
        'error.generation': 'Error during generation',
        'error.interrupted': 'The connection was interrupted unexpectedly. Please try again.',
    },
    es: {
        'header.github': 'Ver el código en GitHub',
        'header.apiKey': 'Clave API',
        'header.theme': 'Cambiar tema claro/oscuro',
        'header.language': 'Idioma',
        'header.subtitle': 'Tu tutor de geometría interactivo y automatizado.',

        'prompt.label': '¿Qué quieres calcular o dibujar?',
        'prompt.placeholder': 'Ej.: Dibuja un triángulo rectángulo y su circunferencia circunscrita.',
        'prompt.overLimit': 'Superaste el límite máximo de {n} caracteres. Acorta tu texto para continuar.',
        'image.attach': 'Adjuntar imagen (opcional)',
        'image.remove': 'Quitar imagen',

        'voice.label': 'Voz del profesor',
        'voice.basic': 'Voces básicas (gTTS)',
        'voice.more': 'Más voces (edgeTTS)',
        'voice.auto': 'Detectar idioma automáticamente (IA)',
        'voice.spanishFemale': 'Español (solo voz femenina)',
        'voice.englishFemale': 'Inglés (solo voz femenina)',
        'voice.spanish': 'Español',
        'voice.english': 'Inglés',
        'voice.male': 'Hombre',
        'voice.female': 'Mujer',

        'model.label': 'Modelo de IA',
        'model.auto': 'Auto (detecta fórmula o razonamiento)',
        'explain.label': 'Explica más',
        'explain.hint': 'Cada paso explica qué se hace, por qué y qué significa el resultado. La lección será más larga y tardará un poco más.',
        'model.autoHint': 'Los ejercicios de fórmula se resuelven con GPT-4o. Los de razonamiento (balanceo de líneas, optimización, secuenciación...) van directo a Claude Sonnet 5.5 y pueden tardar hasta un minuto por su complejidad.',
        'difficulty.formula': 'Fórmula',
        'difficulty.reasoning': 'Razonamiento',
        'difficulty.manual': 'Manual',
        'progress.reasoning': 'Ejercicio de razonamiento: se resuelve con Claude Sonnet 5.5 y puede tardar hasta un minuto...',
        'model.advanced': 'Matemáticas avanzadas y visión',
        'model.basic': 'Matemáticas básicas',
        'model.badge': 'Modelo',
        'lesson.checksFailed': 'Las comprobaciones de esta lección encontraron una condición que su solución no cumple, así que el resultado podría ser incorrecto. Revísalo antes de darlo por bueno.',
        'provider.fatal': 'No se pudo generar la lección: {reason}.',
        'provider.warning': 'El proveedor del modelo de IA tuvo problemas al generar esta lección: {reasons}.',
        'provider.reason.credits': 'la cuenta del proveedor (OpenRouter) no tiene crédito suficiente',
        'provider.reason.rate_limit': 'el proveedor está limitando las peticiones, espera un momento y vuelve a intentarlo',
        'provider.reason.timeout': 'el proveedor tardó demasiado en responder',
        'provider.reason.unavailable': 'el proveedor del modelo no está disponible en este momento',
        'provider.reason.moderation': 'el proveedor rechazó la petición por sus filtros de contenido',
        'provider.reason.auth': 'la clave de API no es válida',
        'provider.reason.truncated': 'la respuesta del modelo se cortó por su límite de longitud',
        'provider.reason.empty': 'el modelo devolvió una respuesta vacía',
        'provider.reason.review_failed': 'el revisor no pudo verificar la lección',
        'provider.reason.provider': 'el proveedor del modelo devolvió un error',

        'generate.idle': 'Generar lección',
        'generate.busy': 'Generando lección...',

        'player.title': 'Controles de reproducción',
        'player.restart': 'Reiniciar',
        'player.next': 'Siguiente paso',
        'download.button': 'Descargar lección',
        'download.notReady': 'Termina la lección para descargarla.',
        'download.failed': 'No se pudo crear el archivo de la lección. Inténtalo de nuevo.',

        'export.fileFallback': 'leccion',
        'export.photoTitle': 'Ejercicio de una foto',
        'export.generated': 'Generada el {date}',
        'export.model': 'Modelo: {model}',
        'export.exercise': 'Ejercicio',
        'export.photoAlt': 'Foto del ejercicio',
        'export.board': 'Pizarra de GeoGebra',
        'export.loading': 'Cargando GeoGebra...',
        'export.offline': 'GeoGebra no pudo cargarse: necesita conexión a internet. Esta es la imagen de la pizarra final.',
        'export.final': 'Ver resultado final',
        'export.finalStatus': 'Pizarra con el resultado final',
        'export.stepStatus': 'Pizarra en el paso {n} de {total}',
        'export.graphAlt': 'Pizarra final de la lección',
        'export.ggb': 'Descargar archivo .ggb',
        'export.ggbHint': 'Se abre en la app de GeoGebra o en geogebra.org/classic',
        'export.print': 'Imprimir o guardar como PDF',
        'export.steps': 'Paso a paso',
        'export.boardHint': 'Usa «Ver en la pizarra» en cualquier paso para ver la pizarra en ese punto de la lección.',
        'export.explanation': 'Explicación',
        'export.show': 'Ver en la pizarra',
        'export.listen': '▶ Escuchar',
        'export.stop': '■ Detener',
        'export.footer': 'Lección generada por TutorGebra',

        'board.title': 'Tablero interactivo',
        'board.fullscreen': 'Pantalla completa',
        'board.empty': 'Escribe tu consulta para cargar el motor.',

        'footer.createdBy': 'Creado por',
        'footer.license': 'Sin fines de lucro, licencia MIT.',

        'select.placeholder': 'Seleccionar...',
        'examples.title': 'Ideas / Ejemplos',
        'examples.use': 'Haz clic para usar este ejemplo',

        'tips.title': '¿Sabías que...?',
        'tips.1': 'El modelo gpt-4o-mini puede alucinar con problemas complejos. Recomendamos usar gpt-4o.',
        'tips.2': '¡Dale una estrella al repositorio en GitHub! ⭐',
        'tips.3': '¿Ves un error o una alucinación? ¡Abre un issue y lo revisamos!',
        'tips.4': '¿Tienes una clave API de OpenRouter? ¡Puedes usarla!',
        'tips.5': '¡Abre una discusión en GitHub para sugerir cambios o nuevas funciones!',
        'tips.6': '¡Buscamos ayuda experta para mejorar la aplicación! Las contribuciones son bienvenidas.',

        'modal.title': 'Clave API de OpenRouter',
        'modal.optional': '(Opcional)',
        'modal.close': 'Cerrar',
        'modal.placeholder': 'Déjalo vacío para usar la clave gratuita del servidor',
        'modal.serverNote': 'Usa la clave del servidor por defecto. Ingresa la tuya para tener cuota privada.',
        'modal.clear': 'Borrar clave',
        'modal.intro': 'TutorGebra necesita un "cerebro" para leer tus ejercicios y convertirlos en código geométrico. Usamos <strong>OpenRouter</strong> para enviar tus solicitudes a los mejores modelos de IA gratuitos disponibles (como Gemini). Si la clave del servidor se agota, puedes usar tu propia clave personal.',
        'modal.secure': '<strong>100% seguro:</strong> tu clave funciona como un puente directo entre tú y OpenRouter. Nunca registramos, recopilamos ni guardamos tu clave en nuestros servidores.',
        'modal.stepsTitle': 'Pasos para obtener tu clave (¡es gratis!):',
        'modal.step1': 'Ve a <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 hover:underline font-semibold">OpenRouter.ai</a>.',
        'modal.step2': 'Inicia sesión con tu cuenta de Google o GitHub.',
        'modal.step3': 'Haz clic en el botón <strong>"Create Key"</strong>.',
        'modal.step4': 'Copia el código generado y pégalo en TutorGebra.',
        'modal.done': 'Listo',

        'progress.starting': 'Iniciando...',
        'progress.thinking': 'Pensando en la solución matemática...',
        'progress.evaluating': 'Comprobando los valores en el tablero...',
        'progress.generated': 'Lección generada ({n} pasos). Sintetizando la voz del profesor...',
        'progress.audioStep': 'Sintetizando el audio del paso {a}/{b}...',

        'error.notImage': 'El archivo seleccionado no es una imagen.',
        'error.imageTooLarge': 'La imagen es demasiado grande, incluso después de comprimirla.',
        'error.imageUnreadable': 'No se pudo leer la imagen.',
        'error.server': 'Error del servidor',
        'error.generation': 'Error durante la generación',
        'error.interrupted': 'La conexión se interrumpió inesperadamente. Intenta nuevamente.',
    },
};

// t('key', { n: 3 }) -> translated text for the current language (falls back to English, then the key).
export function t(key, params) {
    let text = messages[lang.value]?.[key] ?? messages.en[key] ?? key;
    if (params) text = text.replace(/\{(\w+)\}/g, (m, name) => (name in params ? params[name] : m));
    return text;
}

export function setLang(code) {
    if (!LANGS.includes(code)) return;
    lang.value = code;
    document.documentElement.lang = code;
}

// Progress messages come from the server in English (app/routers/exercises.py); translate them here.
export function translateProgress(message) {
    if (!message) return '';
    if (message === 'Thinking about the mathematical solution...') return t('progress.thinking');
    // Sent by app/routers/exercises.py (REASONING_PROGRESS) when Auto routes the exercise to Claude Sonnet
    if (message === 'Reasoning exercise detected: it is solved with Claude Sonnet 5.5 and may take up to a minute...') return t('progress.reasoning');
    // Set by app.js itself while the lesson runs in GeoGebra before the voice is synthesized
    if (message === 'Checking the values on the board...') return t('progress.evaluating');
    let m = message.match(/^Lesson generated \((\d+) steps\)\. Synthesizing teacher voice\.\.\.$/);
    if (m) return t('progress.generated', { n: m[1] });
    m = message.match(/^Synthesizing audio step (\d+)\/(\d+)\.\.\.$/);
    if (m) return t('progress.audioStep', { a: m[1], b: m[2] });
    return message;
}
