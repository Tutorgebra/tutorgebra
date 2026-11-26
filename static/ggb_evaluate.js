// Runs a lesson's commands in a GeoGebra applet without playing it, to read the values GeoGebra really
// computes. The server puts them into the speeches' {name} placeholders before synthesizing the voice
// (POST /api/voice), so every number the student hears is the one on the board.
// Shared by static/app.js and by the local benchmark in exercises_test/ (headless browser, kept out of the repo), so both run the same code.

// GeoGebra requires colons for equation labels ("line1: y = x - 1"), not "line1 = y = x - 1". Only a lone '='
// counts, so a check such as "checkStation1 = station1Time <= taktTime" stays an assignment (same rule as
// sanitize_geogebra_command in app/agent.py).
export function prepareCommand(rawCmd) {
    let cmd = (rawCmd || '').trim();
    const doubleEqualsMatch = cmd.match(/^([a-zA-Z][a-zA-Z0-9]*)\s*=\s*([^=]*?(?<![<>!=])=(?!=).*)$/);
    if (doubleEqualsMatch) {
        cmd = `${doubleEqualsMatch[1]}: ${doubleEqualsMatch[2]}`;
    }
    return cmd;
}

// Object types whose getValue() is the number a lesson talks about (a segment's length, a polygon's area)
// 'boolean' is a lesson's check (checkStation1 = station1Time <= taktTime): getValue() gives 1 or 0
const NUMERIC_TYPES = new Set(['numeric', 'angle', 'segment', 'polygon', 'triangle', 'quadrilateral', 'pentagon', 'hexagon', 'boolean']);
const COORDINATE_TYPES = new Set(['point', 'vector']);

// { value } when the object has one; { pending: true } when it is a number or point that is not computed yet
// (GeoGebra's symbolic engine answers Limit, Integral... asynchronously); {} when it will never have one.
function readValue(api, name) {
    if (!api.exists(name)) return {};
    const type = (api.getObjectType(name) || '').toLowerCase();
    if (COORDINATE_TYPES.has(type)) {
        const x = api.getXcoord(name), y = api.getYcoord(name);
        return Number.isFinite(x) && Number.isFinite(y) ? { value: [x, y] } : { pending: true };
    }
    if (NUMERIC_TYPES.has(type)) {
        let value = api.getValue(name);
        if (type === 'angle') value = value * 180 / Math.PI; // getValue gives radians; lessons speak in degrees
        return Number.isFinite(value) ? { value } : { pending: true };
    }
    return {}; // lines, functions, texts...: the server falls back to its own evaluation
}

const PENDING_WAIT_MS = 1500;
const PENDING_POLL_MS = 100;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Commands that change the view or the style but create no object. evalCommand() reports false for them
// even when they work (ZoomIn, SetVisibleInView, ShowGrid, SetLineStyle...), so its result means nothing here.
const NO_OBJECT_COMMAND_RE = /^(?:Set[A-Z]\w*|Show[A-Z]\w*|Hide[A-Z]\w*|Zoom(?:In|Out)|StartAnimation|Pan|CenterView|Delete|Rename|UpdateConstruction|Execute|PlaySound|StartLogging|StopLogging)\s*\(/;
// "name = ...", "name: y = ...", "funcF(x) = ..." define an object called name
const DEFINED_NAME_RE = /^\s*([A-Za-z][A-Za-z0-9]*)\s*(?:\(\s*[A-Za-z][A-Za-z0-9]*\s*\))?\s*[:=](?!=)/;

function commandFailed(api, cmd, accepted) {
    if (NO_OBJECT_COMMAND_RE.test(cmd)) return false;
    const defined = cmd.match(DEFINED_NAME_RE);
    if (defined) return !api.exists(defined[1]); // an assignment failed if its object does not exist
    return !accepted; // an unnamed object (Polygon(A, B, C), Focus(parab1)...)
}

// Resolves to { values: {name: number | [x, y]}, failed: [indexes of the commands GeoGebra rejected] }.
// Waits up to PENDING_WAIT_MS only if some value is still being computed. Repainting is off meanwhile, so
// the student never sees the finished lesson flash on the board; the applet is left empty, ready to play.
export async function evaluateLesson(api, commands, names) {
    const canPausePainting = typeof api.setRepaintingActive === 'function';
    if (canPausePainting) api.setRepaintingActive(false);
    try {
        api.reset();
        const failed = [];
        (commands || []).forEach((rawCmd, index) => {
            const cmd = prepareCommand(rawCmd);
            if (cmd && commandFailed(api, cmd, api.evalCommand(cmd))) failed.push(index);
        });

        const values = {};
        let pending = [...new Set(names || [])];
        const deadline = Date.now() + PENDING_WAIT_MS;
        while (pending.length) {
            const stillPending = [];
            for (const name of pending) {
                const result = readValue(api, name);
                if (result.value !== undefined) values[name] = result.value;
                else if (result.pending) stillPending.push(name);
            }
            pending = stillPending;
            if (!pending.length || Date.now() >= deadline) break;
            await sleep(PENDING_POLL_MS);
        }
        return { values, failed };
    } finally {
        api.reset();
        if (canPausePainting) api.setRepaintingActive(true);
    }
}
