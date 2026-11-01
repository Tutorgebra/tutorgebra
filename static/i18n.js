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
        'model.auto': 'Auto (Smart Routing)',
        'model.advanced': 'Advanced Math & Vision',
        'model.basic': 'Basic Math',
        'model.badge': 'Model',

        'generate.idle': 'Generate Lesson',
        'generate.busy': 'Generating lesson...',

        'player.title': 'Player Controls',
        'player.restart': 'Restart',
        'player.next': 'Next Step',

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
        'model.auto': 'Auto (enrutamiento inteligente)',
        'model.advanced': 'Matemáticas avanzadas y visión',
        'model.basic': 'Matemáticas básicas',
        'model.badge': 'Modelo',

        'generate.idle': 'Generar lección',
        'generate.busy': 'Generando lección...',

        'player.title': 'Controles de reproducción',
        'player.restart': 'Reiniciar',
        'player.next': 'Siguiente paso',

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
    let m = message.match(/^Lesson generated \((\d+) steps\)\. Synthesizing teacher voice\.\.\.$/);
    if (m) return t('progress.generated', { n: m[1] });
    m = message.match(/^Synthesizing audio step (\d+)\/(\d+)\.\.\.$/);
    if (m) return t('progress.audioStep', { a: m[1], b: m[2] });
    return message;
}
