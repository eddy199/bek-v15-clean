import { fileURLToPath as __eveFileURLToPath } from "node:url";
import { dirname as __eveDirname } from "node:path";
const __filename = __eveFileURLToPath(import.meta.url);
__eveDirname(__filename);
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/tslib.mjs
function __classPrivateFieldSet(receiver, state, value, kind, f) {
	if (kind === "m") throw new TypeError("Private method is not writable");
	if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a setter");
	if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot write private member to an object whose class did not declare it");
	return kind === "a" ? f.call(receiver, value) : f ? f.value = value : state.set(receiver, value), value;
}
function __classPrivateFieldGet(receiver, state, kind, f) {
	if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a getter");
	if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot read private member from an object whose class did not declare it");
	return kind === "m" ? f : kind === "a" ? f.call(receiver) : f ? f.value : state.get(receiver);
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/uuid.mjs
/**
* https://stackoverflow.com/a/2117523
*/
let uuid4 = function() {
	const { crypto } = globalThis;
	if (crypto?.randomUUID) {
		uuid4 = crypto.randomUUID.bind(crypto);
		return crypto.randomUUID();
	}
	const u8 = /* @__PURE__ */ new Uint8Array(1);
	const randomByte = crypto ? () => crypto.getRandomValues(u8)[0] : () => Math.random() * 255 & 255;
	return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) => (+c ^ randomByte() & 15 >> +c / 4).toString(16));
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/errors.mjs
function isAbortError(err) {
	return typeof err === "object" && err !== null && ("name" in err && err.name === "AbortError" || "message" in err && String(err.message).includes("FetchRequestCanceledException"));
}
const castToError = (err) => {
	if (err instanceof Error) return err;
	if (typeof err === "object" && err !== null) {
		try {
			if (Object.prototype.toString.call(err) === "[object Error]") {
				const error = new Error(err.message, err.cause ? { cause: err.cause } : {});
				if (err.stack) error.stack = err.stack;
				if (err.cause && !error.cause) error.cause = err.cause;
				if (err.name) error.name = err.name;
				return error;
			}
		} catch {}
		try {
			return new Error(JSON.stringify(err));
		} catch {}
	}
	return new Error(err);
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/core/error.mjs
var ContextDevError = class extends Error {};
var APIError = class APIError extends ContextDevError {
	constructor(status, error, message, headers) {
		super(`${APIError.makeMessage(status, error, message)}`);
		this.status = status;
		this.headers = headers;
		this.error = error;
	}
	static makeMessage(status, error, message) {
		const msg = error?.message ? typeof error.message === "string" ? error.message : JSON.stringify(error.message) : error ? JSON.stringify(error) : message;
		if (status && msg) return `${status} ${msg}`;
		if (status) return `${status} status code (no body)`;
		if (msg) return msg;
		return "(no status code or body)";
	}
	static generate(status, errorResponse, message, headers) {
		if (!status || !headers) return new APIConnectionError({
			message,
			cause: castToError(errorResponse)
		});
		const error = errorResponse;
		if (status === 400) return new BadRequestError(status, error, message, headers);
		if (status === 401) return new AuthenticationError(status, error, message, headers);
		if (status === 403) return new PermissionDeniedError(status, error, message, headers);
		if (status === 404) return new NotFoundError(status, error, message, headers);
		if (status === 409) return new ConflictError(status, error, message, headers);
		if (status === 422) return new UnprocessableEntityError(status, error, message, headers);
		if (status === 429) return new RateLimitError(status, error, message, headers);
		if (status >= 500) return new InternalServerError(status, error, message, headers);
		return new APIError(status, error, message, headers);
	}
};
var APIUserAbortError = class extends APIError {
	constructor({ message } = {}) {
		super(void 0, void 0, message || "Request was aborted.", void 0);
	}
};
var APIConnectionError = class extends APIError {
	constructor({ message, cause }) {
		super(void 0, void 0, message || "Connection error.", void 0);
		if (cause) this.cause = cause;
	}
};
var APIConnectionTimeoutError = class extends APIConnectionError {
	constructor({ message } = {}) {
		super({ message: message ?? "Request timed out." });
	}
};
var BadRequestError = class extends APIError {};
var AuthenticationError = class extends APIError {};
var PermissionDeniedError = class extends APIError {};
var NotFoundError = class extends APIError {};
var ConflictError = class extends APIError {};
var UnprocessableEntityError = class extends APIError {};
var RateLimitError = class extends APIError {};
var InternalServerError = class extends APIError {};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/values.mjs
const startsWithSchemeRegexp = /^[a-z][a-z0-9+.-]*:/i;
const isAbsoluteURL = (url) => {
	return startsWithSchemeRegexp.test(url);
};
let isArray = (val) => (isArray = Array.isArray, isArray(val));
let isReadonlyArray = isArray;
function isEmptyObj(obj) {
	if (!obj) return true;
	for (const _k in obj) return false;
	return true;
}
function hasOwn(obj, key) {
	return Object.prototype.hasOwnProperty.call(obj, key);
}
const validatePositiveInteger = (name, n) => {
	if (typeof n !== "number" || !Number.isInteger(n)) throw new ContextDevError(`${name} must be an integer`);
	if (n < 0) throw new ContextDevError(`${name} must be a positive integer`);
	return n;
};
const safeJSON = (text) => {
	try {
		return JSON.parse(text);
	} catch (err) {
		return;
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/sleep.mjs
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/detect-platform.mjs
/**
* Note this does not detect 'browser'; for that, use getBrowserInfo().
*/
function getDetectedPlatform() {
	if (typeof Deno !== "undefined" && Deno.build != null) return "deno";
	if (typeof EdgeRuntime !== "undefined") return "edge";
	if (Object.prototype.toString.call(typeof globalThis.process !== "undefined" ? globalThis.process : 0) === "[object process]") return "node";
	return "unknown";
}
const getPlatformProperties = () => {
	const detectedPlatform = getDetectedPlatform();
	if (detectedPlatform === "deno") return {
		"X-Stainless-Lang": "js",
		"X-Stainless-Package-Version": "2.7.0",
		"X-Stainless-OS": normalizePlatform(Deno.build.os),
		"X-Stainless-Arch": normalizeArch(Deno.build.arch),
		"X-Stainless-Runtime": "deno",
		"X-Stainless-Runtime-Version": typeof Deno.version === "string" ? Deno.version : Deno.version?.deno ?? "unknown"
	};
	if (typeof EdgeRuntime !== "undefined") return {
		"X-Stainless-Lang": "js",
		"X-Stainless-Package-Version": "2.7.0",
		"X-Stainless-OS": "Unknown",
		"X-Stainless-Arch": `other:${EdgeRuntime}`,
		"X-Stainless-Runtime": "edge",
		"X-Stainless-Runtime-Version": globalThis.process.version
	};
	if (detectedPlatform === "node") return {
		"X-Stainless-Lang": "js",
		"X-Stainless-Package-Version": "2.7.0",
		"X-Stainless-OS": normalizePlatform(globalThis.process.platform ?? "unknown"),
		"X-Stainless-Arch": normalizeArch(globalThis.process.arch ?? "unknown"),
		"X-Stainless-Runtime": "node",
		"X-Stainless-Runtime-Version": globalThis.process.version ?? "unknown"
	};
	const browserInfo = getBrowserInfo();
	if (browserInfo) return {
		"X-Stainless-Lang": "js",
		"X-Stainless-Package-Version": "2.7.0",
		"X-Stainless-OS": "Unknown",
		"X-Stainless-Arch": "unknown",
		"X-Stainless-Runtime": `browser:${browserInfo.browser}`,
		"X-Stainless-Runtime-Version": browserInfo.version
	};
	return {
		"X-Stainless-Lang": "js",
		"X-Stainless-Package-Version": "2.7.0",
		"X-Stainless-OS": "Unknown",
		"X-Stainless-Arch": "unknown",
		"X-Stainless-Runtime": "unknown",
		"X-Stainless-Runtime-Version": "unknown"
	};
};
function getBrowserInfo() {
	if (typeof navigator === "undefined" || !navigator) return null;
	for (const { key, pattern } of [
		{
			key: "edge",
			pattern: /Edge(?:\W+(\d+)\.(\d+)(?:\.(\d+))?)?/
		},
		{
			key: "ie",
			pattern: /MSIE(?:\W+(\d+)\.(\d+)(?:\.(\d+))?)?/
		},
		{
			key: "ie",
			pattern: /Trident(?:.*rv\:(\d+)\.(\d+)(?:\.(\d+))?)?/
		},
		{
			key: "chrome",
			pattern: /Chrome(?:\W+(\d+)\.(\d+)(?:\.(\d+))?)?/
		},
		{
			key: "firefox",
			pattern: /Firefox(?:\W+(\d+)\.(\d+)(?:\.(\d+))?)?/
		},
		{
			key: "safari",
			pattern: /(?:Version\W+(\d+)\.(\d+)(?:\.(\d+))?)?(?:\W+Mobile\S*)?\W+Safari/
		}
	]) {
		const match = pattern.exec(navigator.userAgent);
		if (match) return {
			browser: key,
			version: `${match[1] || 0}.${match[2] || 0}.${match[3] || 0}`
		};
	}
	return null;
}
const normalizeArch = (arch) => {
	if (arch === "x32") return "x32";
	if (arch === "x86_64" || arch === "x64") return "x64";
	if (arch === "arm") return "arm";
	if (arch === "aarch64" || arch === "arm64") return "arm64";
	if (arch) return `other:${arch}`;
	return "unknown";
};
const normalizePlatform = (platform) => {
	platform = platform.toLowerCase();
	if (platform.includes("ios")) return "iOS";
	if (platform === "android") return "Android";
	if (platform === "darwin") return "MacOS";
	if (platform === "win32") return "Windows";
	if (platform === "freebsd") return "FreeBSD";
	if (platform === "openbsd") return "OpenBSD";
	if (platform === "linux") return "Linux";
	if (platform) return `Other:${platform}`;
	return "Unknown";
};
let _platformHeaders;
const getPlatformHeaders = () => {
	return _platformHeaders ?? (_platformHeaders = getPlatformProperties());
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/shims.mjs
function getDefaultFetch() {
	if (typeof fetch !== "undefined") return fetch;
	throw new Error("`fetch` is not defined as a global; Either pass `fetch` to the client, `new ContextDev({ fetch })` or polyfill the global, `globalThis.fetch = fetch`");
}
function makeReadableStream(...args) {
	const ReadableStream = globalThis.ReadableStream;
	if (typeof ReadableStream === "undefined") throw new Error("`ReadableStream` is not defined as a global; You will need to polyfill it, `globalThis.ReadableStream = ReadableStream`");
	return new ReadableStream(...args);
}
function ReadableStreamFrom(iterable) {
	let iter = Symbol.asyncIterator in iterable ? iterable[Symbol.asyncIterator]() : iterable[Symbol.iterator]();
	return makeReadableStream({
		start() {},
		async pull(controller) {
			const { done, value } = await iter.next();
			if (done) controller.close();
			else controller.enqueue(value);
		},
		async cancel() {
			await iter.return?.();
		}
	});
}
/**
* Cancels a ReadableStream we don't need to consume.
* See https://undici.nodejs.org/#/?id=garbage-collection
*/
async function CancelReadableStream(stream) {
	if (stream === null || typeof stream !== "object") return;
	if (stream[Symbol.asyncIterator]) {
		await stream[Symbol.asyncIterator]().return?.();
		return;
	}
	const reader = stream.getReader();
	const cancelPromise = reader.cancel();
	reader.releaseLock();
	await cancelPromise;
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/request-options.mjs
const FallbackEncoder = ({ headers, body }) => {
	return {
		bodyHeaders: { "content-type": "application/json" },
		body: JSON.stringify(body)
	};
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/qs/formats.mjs
const default_formatter = (v) => String(v);
const formatters = {
	RFC1738: (v) => String(v).replace(/%20/g, "+"),
	RFC3986: default_formatter
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/qs/utils.mjs
let has = (obj, key) => (has = Object.hasOwn ?? Function.prototype.call.bind(Object.prototype.hasOwnProperty), has(obj, key));
const hex_table = /* @__PURE__ */ (() => {
	const array = [];
	for (let i = 0; i < 256; ++i) array.push("%" + ((i < 16 ? "0" : "") + i.toString(16)).toUpperCase());
	return array;
})();
const limit = 1024;
const encode = (str, _defaultEncoder, charset, _kind, format) => {
	if (str.length === 0) return str;
	let string = str;
	if (typeof str === "symbol") string = Symbol.prototype.toString.call(str);
	else if (typeof str !== "string") string = String(str);
	if (charset === "iso-8859-1") return escape(string).replace(/%u[0-9a-f]{4}/gi, function($0) {
		return "%26%23" + parseInt($0.slice(2), 16) + "%3B";
	});
	let out = "";
	for (let j = 0; j < string.length; j += limit) {
		const segment = string.length >= limit ? string.slice(j, j + limit) : string;
		const arr = [];
		for (let i = 0; i < segment.length; ++i) {
			let c = segment.charCodeAt(i);
			if (c === 45 || c === 46 || c === 95 || c === 126 || c >= 48 && c <= 57 || c >= 65 && c <= 90 || c >= 97 && c <= 122 || format === "RFC1738" && (c === 40 || c === 41)) {
				arr[arr.length] = segment.charAt(i);
				continue;
			}
			if (c < 128) {
				arr[arr.length] = hex_table[c];
				continue;
			}
			if (c < 2048) {
				arr[arr.length] = hex_table[192 | c >> 6] + hex_table[128 | c & 63];
				continue;
			}
			if (c < 55296 || c >= 57344) {
				arr[arr.length] = hex_table[224 | c >> 12] + hex_table[128 | c >> 6 & 63] + hex_table[128 | c & 63];
				continue;
			}
			i += 1;
			c = 65536 + ((c & 1023) << 10 | segment.charCodeAt(i) & 1023);
			arr[arr.length] = hex_table[240 | c >> 18] + hex_table[128 | c >> 12 & 63] + hex_table[128 | c >> 6 & 63] + hex_table[128 | c & 63];
		}
		out += arr.join("");
	}
	return out;
};
function is_buffer(obj) {
	if (!obj || typeof obj !== "object") return false;
	return !!(obj.constructor && obj.constructor.isBuffer && obj.constructor.isBuffer(obj));
}
function maybe_map(val, fn) {
	if (isArray(val)) {
		const mapped = [];
		for (let i = 0; i < val.length; i += 1) mapped.push(fn(val[i]));
		return mapped;
	}
	return fn(val);
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/qs/stringify.mjs
const array_prefix_generators = {
	brackets(prefix) {
		return String(prefix) + "[]";
	},
	comma: "comma",
	indices(prefix, key) {
		return String(prefix) + "[" + key + "]";
	},
	repeat(prefix) {
		return String(prefix);
	}
};
const push_to_array = function(arr, value_or_array) {
	Array.prototype.push.apply(arr, isArray(value_or_array) ? value_or_array : [value_or_array]);
};
let toISOString;
const defaults = {
	addQueryPrefix: false,
	allowDots: false,
	allowEmptyArrays: false,
	arrayFormat: "indices",
	charset: "utf-8",
	charsetSentinel: false,
	delimiter: "&",
	encode: true,
	encodeDotInKeys: false,
	encoder: encode,
	encodeValuesOnly: false,
	format: "RFC3986",
	formatter: default_formatter,
	/** @deprecated */
	indices: false,
	serializeDate(date) {
		return (toISOString ?? (toISOString = Function.prototype.call.bind(Date.prototype.toISOString)))(date);
	},
	skipNulls: false,
	strictNullHandling: false
};
function is_non_nullish_primitive(v) {
	return typeof v === "string" || typeof v === "number" || typeof v === "boolean" || typeof v === "symbol" || typeof v === "bigint";
}
const sentinel = {};
function inner_stringify(object, prefix, generateArrayPrefix, commaRoundTrip, allowEmptyArrays, strictNullHandling, skipNulls, encodeDotInKeys, encoder, filter, sort, allowDots, serializeDate, format, formatter, encodeValuesOnly, charset, sideChannel) {
	let obj = object;
	let tmp_sc = sideChannel;
	let step = 0;
	let find_flag = false;
	while ((tmp_sc = tmp_sc.get(sentinel)) !== void 0 && !find_flag) {
		const pos = tmp_sc.get(object);
		step += 1;
		if (typeof pos !== "undefined") if (pos === step) throw new RangeError("Cyclic object value");
		else find_flag = true;
		if (typeof tmp_sc.get(sentinel) === "undefined") step = 0;
	}
	if (typeof filter === "function") obj = filter(prefix, obj);
	else if (obj instanceof Date) obj = serializeDate?.(obj);
	else if (generateArrayPrefix === "comma" && isArray(obj)) obj = maybe_map(obj, function(value) {
		if (value instanceof Date) return serializeDate?.(value);
		return value;
	});
	if (obj === null) {
		if (strictNullHandling) return encoder && !encodeValuesOnly ? encoder(prefix, defaults.encoder, charset, "key", format) : prefix;
		obj = "";
	}
	if (is_non_nullish_primitive(obj) || is_buffer(obj)) {
		if (encoder) {
			const key_value = encodeValuesOnly ? prefix : encoder(prefix, defaults.encoder, charset, "key", format);
			return [formatter?.(key_value) + "=" + formatter?.(encoder(obj, defaults.encoder, charset, "value", format))];
		}
		return [formatter?.(prefix) + "=" + formatter?.(String(obj))];
	}
	const values = [];
	if (typeof obj === "undefined") return values;
	let obj_keys;
	if (generateArrayPrefix === "comma" && isArray(obj)) {
		if (encodeValuesOnly && encoder) obj = maybe_map(obj, encoder);
		obj_keys = [{ value: obj.length > 0 ? obj.join(",") || null : void 0 }];
	} else if (isArray(filter)) obj_keys = filter;
	else {
		const keys = Object.keys(obj);
		obj_keys = sort ? keys.sort(sort) : keys;
	}
	const encoded_prefix = encodeDotInKeys ? String(prefix).replace(/\./g, "%2E") : String(prefix);
	const adjusted_prefix = commaRoundTrip && isArray(obj) && obj.length === 1 ? encoded_prefix + "[]" : encoded_prefix;
	if (allowEmptyArrays && isArray(obj) && obj.length === 0) return adjusted_prefix + "[]";
	for (let j = 0; j < obj_keys.length; ++j) {
		const key = obj_keys[j];
		const value = typeof key === "object" && typeof key.value !== "undefined" ? key.value : obj[key];
		if (skipNulls && value === null) continue;
		const encoded_key = allowDots && encodeDotInKeys ? key.replace(/\./g, "%2E") : key;
		const key_prefix = isArray(obj) ? typeof generateArrayPrefix === "function" ? generateArrayPrefix(adjusted_prefix, encoded_key) : adjusted_prefix : adjusted_prefix + (allowDots ? "." + encoded_key : "[" + encoded_key + "]");
		sideChannel.set(object, step);
		const valueSideChannel = /* @__PURE__ */ new WeakMap();
		valueSideChannel.set(sentinel, sideChannel);
		push_to_array(values, inner_stringify(value, key_prefix, generateArrayPrefix, commaRoundTrip, allowEmptyArrays, strictNullHandling, skipNulls, encodeDotInKeys, generateArrayPrefix === "comma" && encodeValuesOnly && isArray(obj) ? null : encoder, filter, sort, allowDots, serializeDate, format, formatter, encodeValuesOnly, charset, valueSideChannel));
	}
	return values;
}
function normalize_stringify_options(opts = defaults) {
	if (typeof opts.allowEmptyArrays !== "undefined" && typeof opts.allowEmptyArrays !== "boolean") throw new TypeError("`allowEmptyArrays` option can only be `true` or `false`, when provided");
	if (typeof opts.encodeDotInKeys !== "undefined" && typeof opts.encodeDotInKeys !== "boolean") throw new TypeError("`encodeDotInKeys` option can only be `true` or `false`, when provided");
	if (opts.encoder !== null && typeof opts.encoder !== "undefined" && typeof opts.encoder !== "function") throw new TypeError("Encoder has to be a function.");
	const charset = opts.charset || defaults.charset;
	if (typeof opts.charset !== "undefined" && opts.charset !== "utf-8" && opts.charset !== "iso-8859-1") throw new TypeError("The charset option must be either utf-8, iso-8859-1, or undefined");
	let format = "RFC3986";
	if (typeof opts.format !== "undefined") {
		if (!has(formatters, opts.format)) throw new TypeError("Unknown format option provided.");
		format = opts.format;
	}
	const formatter = formatters[format];
	let filter = defaults.filter;
	if (typeof opts.filter === "function" || isArray(opts.filter)) filter = opts.filter;
	let arrayFormat;
	if (opts.arrayFormat && opts.arrayFormat in array_prefix_generators) arrayFormat = opts.arrayFormat;
	else if ("indices" in opts) arrayFormat = opts.indices ? "indices" : "repeat";
	else arrayFormat = defaults.arrayFormat;
	if ("commaRoundTrip" in opts && typeof opts.commaRoundTrip !== "boolean") throw new TypeError("`commaRoundTrip` must be a boolean, or absent");
	const allowDots = typeof opts.allowDots === "undefined" ? !!opts.encodeDotInKeys === true ? true : defaults.allowDots : !!opts.allowDots;
	return {
		addQueryPrefix: typeof opts.addQueryPrefix === "boolean" ? opts.addQueryPrefix : defaults.addQueryPrefix,
		allowDots,
		allowEmptyArrays: typeof opts.allowEmptyArrays === "boolean" ? !!opts.allowEmptyArrays : defaults.allowEmptyArrays,
		arrayFormat,
		charset,
		charsetSentinel: typeof opts.charsetSentinel === "boolean" ? opts.charsetSentinel : defaults.charsetSentinel,
		commaRoundTrip: !!opts.commaRoundTrip,
		delimiter: typeof opts.delimiter === "undefined" ? defaults.delimiter : opts.delimiter,
		encode: typeof opts.encode === "boolean" ? opts.encode : defaults.encode,
		encodeDotInKeys: typeof opts.encodeDotInKeys === "boolean" ? opts.encodeDotInKeys : defaults.encodeDotInKeys,
		encoder: typeof opts.encoder === "function" ? opts.encoder : defaults.encoder,
		encodeValuesOnly: typeof opts.encodeValuesOnly === "boolean" ? opts.encodeValuesOnly : defaults.encodeValuesOnly,
		filter,
		format,
		formatter,
		serializeDate: typeof opts.serializeDate === "function" ? opts.serializeDate : defaults.serializeDate,
		skipNulls: typeof opts.skipNulls === "boolean" ? opts.skipNulls : defaults.skipNulls,
		sort: typeof opts.sort === "function" ? opts.sort : null,
		strictNullHandling: typeof opts.strictNullHandling === "boolean" ? opts.strictNullHandling : defaults.strictNullHandling
	};
}
function stringify(object, opts = {}) {
	let obj = object;
	const options = normalize_stringify_options(opts);
	let obj_keys;
	let filter;
	if (typeof options.filter === "function") {
		filter = options.filter;
		obj = filter("", obj);
	} else if (isArray(options.filter)) {
		filter = options.filter;
		obj_keys = filter;
	}
	const keys = [];
	if (typeof obj !== "object" || obj === null) return "";
	const generateArrayPrefix = array_prefix_generators[options.arrayFormat];
	const commaRoundTrip = generateArrayPrefix === "comma" && options.commaRoundTrip;
	if (!obj_keys) obj_keys = Object.keys(obj);
	if (options.sort) obj_keys.sort(options.sort);
	const sideChannel = /* @__PURE__ */ new WeakMap();
	for (let i = 0; i < obj_keys.length; ++i) {
		const key = obj_keys[i];
		if (options.skipNulls && obj[key] === null) continue;
		push_to_array(keys, inner_stringify(obj[key], key, generateArrayPrefix, commaRoundTrip, options.allowEmptyArrays, options.strictNullHandling, options.skipNulls, options.encodeDotInKeys, options.encode ? options.encoder : null, options.filter, options.sort, options.allowDots, options.serializeDate, options.format, options.formatter, options.encodeValuesOnly, options.charset, sideChannel));
	}
	const joined = keys.join(options.delimiter);
	let prefix = options.addQueryPrefix === true ? "?" : "";
	if (options.charsetSentinel) if (options.charset === "iso-8859-1") prefix += "utf8=%26%2310003%3B&";
	else prefix += "utf8=%E2%9C%93&";
	return joined.length > 0 ? prefix + joined : "";
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/query.mjs
function stringifyQuery(query) {
	return stringify(query, { arrayFormat: "comma" });
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/uploads.mjs
const checkFileSupport = () => {
	if (typeof File === "undefined") {
		const { process } = globalThis;
		const isOldNode = typeof process?.versions?.node === "string" && parseInt(process.versions.node.split(".")) < 20;
		throw new Error("`File` is not defined as a global, which is required for file uploads." + (isOldNode ? " Update to Node 20 LTS or newer, or set `globalThis.File` to `import('node:buffer').File`." : ""));
	}
};
/**
* Construct a `File` instance. This is used to ensure a helpful error is thrown
* for environments that don't define a global `File` yet.
*/
function makeFile(fileBits, fileName, options) {
	checkFileSupport();
	return new File(fileBits, fileName ?? "unknown_file", options);
}
function getName(value) {
	return (typeof value === "object" && value !== null && ("name" in value && value.name && String(value.name) || "url" in value && value.url && String(value.url) || "filename" in value && value.filename && String(value.filename) || "path" in value && value.path && String(value.path)) || "").split(/[\\/]/).pop() || void 0;
}
const isAsyncIterable = (value) => value != null && typeof value === "object" && typeof value[Symbol.asyncIterator] === "function";
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/to-file.mjs
/**
* This check adds the arrayBuffer() method type because it is available and used at runtime
*/
const isBlobLike = (value) => value != null && typeof value === "object" && typeof value.size === "number" && typeof value.type === "string" && typeof value.text === "function" && typeof value.slice === "function" && typeof value.arrayBuffer === "function";
/**
* This check adds the arrayBuffer() method type because it is available and used at runtime
*/
const isFileLike = (value) => value != null && typeof value === "object" && typeof value.name === "string" && typeof value.lastModified === "number" && isBlobLike(value);
const isResponseLike = (value) => value != null && typeof value === "object" && typeof value.url === "string" && typeof value.blob === "function";
/**
* Helper for creating a {@link File} to pass to an SDK upload method from a variety of different data formats
* @param value the raw content of the file. Can be an {@link Uploadable}, BlobLikePart, or AsyncIterable of BlobLikeParts
* @param {string=} name the name of the file. If omitted, toFile will try to determine a file name from bits if possible
* @param {Object=} options additional properties
* @param {string=} options.type the MIME type of the content
* @param {number=} options.lastModified the last modified timestamp
* @returns a {@link File} with the given properties
*/
async function toFile(value, name, options) {
	checkFileSupport();
	value = await value;
	if (isFileLike(value)) {
		if (value instanceof File) return value;
		return makeFile([await value.arrayBuffer()], value.name);
	}
	if (isResponseLike(value)) {
		const blob = await value.blob();
		name || (name = new URL(value.url).pathname.split(/[\\/]/).pop());
		return makeFile(await getBytes(blob), name, options);
	}
	const parts = await getBytes(value);
	name || (name = getName(value));
	if (!options?.type) {
		const type = parts.find((part) => typeof part === "object" && "type" in part && part.type);
		if (typeof type === "string") options = {
			...options,
			type
		};
	}
	return makeFile(parts, name, options);
}
async function getBytes(value) {
	let parts = [];
	if (typeof value === "string" || ArrayBuffer.isView(value) || value instanceof ArrayBuffer) parts.push(value);
	else if (isBlobLike(value)) parts.push(value instanceof Blob ? value : await value.arrayBuffer());
	else if (isAsyncIterable(value)) for await (const chunk of value) parts.push(...await getBytes(chunk));
	else {
		const constructor = value?.constructor?.name;
		throw new Error(`Unexpected data type: ${typeof value}${constructor ? `; constructor: ${constructor}` : ""}${propsForError(value)}`);
	}
	return parts;
}
function propsForError(value) {
	if (typeof value !== "object" || value === null) return "";
	return `; props: [${Object.getOwnPropertyNames(value).map((p) => `"${p}"`).join(", ")}]`;
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/core/resource.mjs
var APIResource = class {
	constructor(client) {
		this._client = client;
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/ai.mjs
var AI = class extends APIResource {
	/**
	* Given a single URL, determines if it is a product page and extracts the product
	* information.
	*
	* @example
	* ```ts
	* const response = await client.ai.extractProduct({
	*   url: 'https://example.com',
	* });
	* ```
	*/
	extractProduct(body, options) {
		return this._client.post("/brand/ai/product", {
			body,
			...options
		});
	}
	/**
	* Extract product information from a brand's website. We will analyze the website
	* and return a list of products with details such as name, description, image,
	* pricing, features, and more.
	*
	* @example
	* ```ts
	* const response = await client.ai.extractProducts({
	*   domain: 'domain',
	* });
	* ```
	*/
	extractProducts(body, options) {
		return this._client.post("/brand/ai/products", {
			body,
			...options
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/path.mjs
/**
* Percent-encode everything that isn't safe to have in a path without encoding safe chars.
*
* Taken from https://datatracker.ietf.org/doc/html/rfc3986#section-3.3:
* > unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"
* > sub-delims  = "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" / "," / ";" / "="
* > pchar       = unreserved / pct-encoded / sub-delims / ":" / "@"
*/
function encodeURIPath(str) {
	return str.replace(/[^A-Za-z0-9\-._~!$&'()*+,;=:@]+/g, encodeURIComponent);
}
const EMPTY = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.create(null));
const createPathTagFunction = (pathEncoder = encodeURIPath) => function path(statics, ...params) {
	if (statics.length === 1) return statics[0];
	let postPath = false;
	const invalidSegments = [];
	const path = statics.reduce((previousValue, currentValue, index) => {
		if (/[?#]/.test(currentValue)) postPath = true;
		const value = params[index];
		let encoded = (postPath ? encodeURIComponent : pathEncoder)("" + value);
		if (index !== params.length && (value == null || typeof value === "object" && value.toString === Object.getPrototypeOf(Object.getPrototypeOf(value.hasOwnProperty ?? EMPTY) ?? EMPTY)?.toString)) {
			encoded = value + "";
			invalidSegments.push({
				start: previousValue.length + currentValue.length,
				length: encoded.length,
				error: `Value of type ${Object.prototype.toString.call(value).slice(8, -1)} is not a valid path parameter`
			});
		}
		return previousValue + currentValue + (index === params.length ? "" : encoded);
	}, "");
	const pathOnly = path.split(/[?#]/, 1)[0];
	const invalidSegmentPattern = /(?<=^|\/)(?:\.|%2e){1,2}(?=\/|$)/gi;
	let match;
	while ((match = invalidSegmentPattern.exec(pathOnly)) !== null) invalidSegments.push({
		start: match.index,
		length: match[0].length,
		error: `Value "${match[0]}" can\'t be safely passed as a path parameter`
	});
	invalidSegments.sort((a, b) => a.start - b.start);
	if (invalidSegments.length > 0) {
		let lastEnd = 0;
		const underline = invalidSegments.reduce((acc, segment) => {
			const spaces = " ".repeat(segment.start - lastEnd);
			const arrows = "^".repeat(segment.length);
			lastEnd = segment.start + segment.length;
			return acc + spaces + arrows;
		}, "");
		throw new ContextDevError(`Path parameters result in path with invalid segments:\n${invalidSegments.map((e) => e.error).join("\n")}\n${path}\n${underline}`);
	}
	return path;
};
/**
* URI-encodes path params and ensures no unsafe /./ or /../ path segments are introduced.
*/
const path = /* @__PURE__ */ createPathTagFunction(encodeURIPath);
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/batch.mjs
var Batch = class extends APIResource {
	/**
	* Check progress and get download links when the batch finishes. Also returns the
	* rejected-URL list and webhook signing secret from submission, so nothing is lost
	* if the submit response was dropped.
	*
	* @example
	* ```ts
	* const batch = await client.batch.retrieve('batch_9f2c8a');
	* ```
	*/
	retrieve(batchID, options) {
		return this._client.get(path`/batch/${batchID}`, options);
	}
	/**
	* List your batches from newest to oldest. Filter by status or continue with a
	* cursor.
	*
	* @example
	* ```ts
	* const batches = await client.batch.list();
	* ```
	*/
	list(query = {}, options) {
		return this._client.get("/batch/list", {
			query,
			...options
		});
	}
	/**
	* Stop a batch from starting new pages. In-progress pages finish, and unused
	* credits are refunded.
	*
	* @example
	* ```ts
	* const response = await client.batch.cancel('batch_9f2c8a');
	* ```
	*/
	cancel(batchID, options) {
		return this._client.post(path`/batch/${batchID}/cancel`, options);
	}
	/**
	* Page through the result records of a finished batch as JSON, in the same order
	* as the downloadable result files. Use this instead of downloading and parsing
	* the NDJSON files yourself.
	*
	* @example
	* ```ts
	* const response = await client.batch.getResults(
	*   'batch_9f2c8a',
	* );
	* ```
	*/
	getResults(batchID, query = {}, options) {
		return this._client.get(path`/batch/${batchID}/results`, {
			query,
			...options
		});
	}
	/**
	* Retrieve and normalize a person profile from identifiers.
	*
	* @example
	* ```ts
	* const response = await client.batch.submit({
	*   identifiers: {
	*     linkedinUrl:
	*       'https://www.linkedin.com/in/yahia-bakour/',
	*   },
	* });
	* ```
	*/
	submit(body, options) {
		return this._client.post("/people/retrieve", {
			body,
			...options
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/brand.mjs
var Brand = class extends APIResource {
	/**
	* Retrieve logos, backdrops, colors, industry, description, and more. Provide
	* exactly one lookup identifier in the request body: a domain, company name, email
	* address, stock ticker, transaction descriptor, or direct URL. Note:
	* `by_direct_url` fetches brand data only from the provided URL — not from the
	* entire internet.
	*
	* @example
	* ```ts
	* const brand = await client.brand.retrieve({
	*   domain: 'stripe.com',
	*   type: 'by_domain',
	* });
	* ```
	*/
	retrieve(body, options) {
		return this._client.post("/brand/retrieve", {
			body,
			...options
		});
	}
	/**
	* Returns a simplified version of brand data containing only essential
	* information: domain, title, colors, logos, and backdrops. Optimized for faster
	* responses and reduced data transfer.
	*
	* @example
	* ```ts
	* const response = await client.brand.retrieveSimplified({
	*   domain: 'xxx',
	* });
	* ```
	*/
	retrieveSimplified(query, options) {
		return this._client.get("/brand/retrieve-simplified", {
			query,
			...options
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/industry.mjs
var Industry = class extends APIResource {
	/**
	* Classify any brand into 2022 NAICS industry codes from its domain or name.
	*/
	retrieveNaics(query, options) {
		return this._client.get("/web/naics", {
			query,
			...options
		});
	}
	/**
	* Classify any brand into Standard Industrial Classification (SIC) codes from its
	* domain or name. Choose between the original SIC system (`original_sic`) or the
	* latest SIC list maintained by the SEC (`latest_sec`).
	*/
	retrieveSic(query, options) {
		return this._client.get("/web/sic", {
			query,
			...options
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/monitors.mjs
/**
* Monitor pages, sitemaps, and extracted website data for exact or semantic changes. Webhook payloads are documented by the MonitorsChangeDetectedWebhookPayload and MonitorsRunCompletedWebhookPayload schemas.
*/
var Monitors = class extends APIResource {
	/**
	* Creates a monitor. The request body is a union of the supported target/change
	* detection combinations. The monitor runs immediately after creation to create
	* its initial baseline.
	*
	* @example
	* ```ts
	* const monitor = await client.monitors.create({
	*   name: 'Acme pricing page',
	*   target: { type: 'page', url: 'https://acme.com/pricing' },
	*   change_detection: { type: 'exact' },
	*   mode: 'web',
	*   schedule: {
	*     type: 'interval',
	*     frequency: 6,
	*     unit: 'hours',
	*   },
	*   webhook: { url: 'https://example.com/webhook' },
	* });
	* ```
	*/
	create(body, options) {
		return this._client.post("/monitors", {
			body,
			...options
		});
	}
	/**
	* Get a monitor
	*
	* @example
	* ```ts
	* const monitor = await client.monitors.retrieve('mon_123');
	* ```
	*/
	retrieve(monitorID, options) {
		return this._client.get(path`/monitors/${monitorID}`, options);
	}
	/**
	* Updates a monitor. If `target` or `change_detection` changes, the monitor
	* creates a new baseline. Unsupported target/change detection combinations are
	* rejected.
	*
	* @example
	* ```ts
	* const monitor = await client.monitors.update('mon_123', {
	*   name: 'Acme pricing monitor',
	*   schedule: {
	*     type: 'interval',
	*     frequency: 1,
	*     unit: 'hours',
	*   },
	*   status: 'active',
	*   webhook: { url: 'https://example.com/webhook' },
	* });
	* ```
	*/
	update(monitorID, body, options) {
		return this._client.patch(path`/monitors/${monitorID}`, {
			body,
			...options
		});
	}
	/**
	* Lists monitors for the authenticated organization. Supports free-text search
	* (`q` over `search_by` fields, `prefix` or `exact` via `search_type`) plus
	* status/type/tag filters. Results are paginated via the opaque `cursor`.
	*
	* @example
	* ```ts
	* const monitors = await client.monitors.list();
	* ```
	*/
	list(query = {}, options) {
		return this._client.get("/monitors", {
			query,
			...options
		});
	}
	/**
	* Delete a monitor
	*
	* @example
	* ```ts
	* const monitor = await client.monitors.delete('mon_123');
	* ```
	*/
	delete(monitorID, options) {
		return this._client.delete(path`/monitors/${monitorID}`, options);
	}
	/**
	* Returns credits charged per monitor over an optional [since, until] window,
	* newest spenders first.
	*
	* @example
	* ```ts
	* const response = await client.monitors.getCreditUsage();
	* ```
	*/
	getCreditUsage(query = {}, options) {
		return this._client.get("/monitors/credit-usage", {
			query,
			...options
		});
	}
	/**
	* Returns how many monitors the account has and the maximum it allows.
	*
	* @example
	* ```ts
	* const response = await client.monitors.getLimits();
	* ```
	*/
	getLimits(options) {
		return this._client.get("/monitors/limits", options);
	}
	/**
	* Returns an account-wide feed of detected changes across monitors.
	*
	* @example
	* ```ts
	* const response = await client.monitors.listAccountChanges();
	* ```
	*/
	listAccountChanges(query = {}, options) {
		return this._client.get("/monitors/changes", {
			query,
			...options
		});
	}
	/**
	* Returns an account-wide feed of monitor runs across all monitors.
	*
	* @example
	* ```ts
	* const response = await client.monitors.listAccountRuns();
	* ```
	*/
	listAccountRuns(query = {}, options) {
		return this._client.get("/monitors/runs", {
			query,
			...options
		});
	}
	/**
	* List changes for a monitor
	*
	* @example
	* ```ts
	* const response = await client.monitors.listChanges(
	*   'mon_123',
	* );
	* ```
	*/
	listChanges(monitorID, query = {}, options) {
		return this._client.get(path`/monitors/${monitorID}/changes`, {
			query,
			...options
		});
	}
	/**
	* List monitor runs
	*
	* @example
	* ```ts
	* const response = await client.monitors.listRuns('mon_123');
	* ```
	*/
	listRuns(monitorID, query = {}, options) {
		return this._client.get(path`/monitors/${monitorID}/runs`, {
			query,
			...options
		});
	}
	/**
	* Get a change
	*
	* @example
	* ```ts
	* const response = await client.monitors.retrieveChange(
	*   'chg_123',
	* );
	* ```
	*/
	retrieveChange(changeID, options) {
		return this._client.get(path`/monitors/changes/${changeID}`, options);
	}
	/**
	* Triggers an immediate run of the monitor outside its normal schedule. The run is
	* queued and processed asynchronously.
	*
	* @example
	* ```ts
	* const response = await client.monitors.run('mon_123');
	* ```
	*/
	run(monitorID, options) {
		return this._client.post(path`/monitors/${monitorID}/run`, options);
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/headers.mjs
const brand_privateNullableHeaders = /* @__PURE__ */ Symbol("brand.privateNullableHeaders");
function* iterateHeaders(headers) {
	if (!headers) return;
	if (brand_privateNullableHeaders in headers) {
		const { values, nulls } = headers;
		yield* values.entries();
		for (const name of nulls) yield [name, null];
		return;
	}
	let shouldClear = false;
	let iter;
	if (headers instanceof Headers) iter = headers.entries();
	else if (isReadonlyArray(headers)) iter = headers;
	else {
		shouldClear = true;
		iter = Object.entries(headers ?? {});
	}
	for (let row of iter) {
		const name = row[0];
		if (typeof name !== "string") throw new TypeError("expected header name to be a string");
		const values = isReadonlyArray(row[1]) ? row[1] : [row[1]];
		let didClear = false;
		for (const value of values) {
			if (value === void 0) continue;
			if (shouldClear && !didClear) {
				didClear = true;
				yield [name, null];
			}
			yield [name, value];
		}
	}
}
const buildHeaders = (newHeaders) => {
	const targetHeaders = new Headers();
	const nullHeaders = /* @__PURE__ */ new Set();
	for (const headers of newHeaders) {
		const seenHeaders = /* @__PURE__ */ new Set();
		for (const [name, value] of iterateHeaders(headers)) {
			const lowerName = name.toLowerCase();
			if (!seenHeaders.has(lowerName)) {
				targetHeaders.delete(name);
				seenHeaders.add(lowerName);
			}
			if (value === null) {
				targetHeaders.delete(name);
				nullHeaders.add(lowerName);
			} else {
				targetHeaders.append(name, value);
				nullHeaders.delete(lowerName);
			}
		}
	}
	return {
		[brand_privateNullableHeaders]: true,
		values: targetHeaders,
		nulls: nullHeaders
	};
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/parse.mjs
var Parse = class extends APIResource {
	/**
	* Converts raw text, source code, web/data, PDF, Microsoft Office, and image bytes
	* into LLM-usable Markdown.
	*/
	handle(body, params, options) {
		const { client, extension, includeImages, includeLinks, ocr, pdf, shortenBase64Images, tags, useMainContentOnly, zdr } = params;
		return this._client.post("/parse", {
			body,
			query: {
				client,
				extension,
				includeImages,
				includeLinks,
				ocr,
				pdf,
				shortenBase64Images,
				tags,
				useMainContentOnly,
				zdr
			},
			...options,
			headers: buildHeaders([{ "Content-Type": "application/octet-stream" }, options?.headers])
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/utility.mjs
var Utility = class extends APIResource {
	/**
	* Signal that you may fetch brand data soon to improve latency. The type field
	* selects what to prefetch (currently only 'brand') and identifier carries exactly
	* one lookup key: a domain, or an email whose domain is extracted and validated
	* (free email providers and disposable email addresses are not allowed).
	*
	* @example
	* ```ts
	* const response = await client.utility.prefetch({
	*   identifier: { domain: 'xxx' },
	*   type: 'brand',
	* });
	* ```
	*/
	prefetch(body, options) {
		return this._client.post("/utility/prefetch", {
			body,
			...options
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/resources/web.mjs
var Web = class extends APIResource {
	/**
	* Crawl a website, use the provided JSON Schema and instructions to prioritize
	* relevant internal links, and extract structured data from the selected pages.
	*
	* @example
	* ```ts
	* const response = await client.web.extract({
	*   schema: {
	*     type: 'bar',
	*     properties: 'bar',
	*     required: 'bar',
	*     additionalProperties: 'bar',
	*   },
	*   url: 'https://example.com',
	* });
	* ```
	*/
	extract(body, options) {
		return this._client.post("/web/extract", {
			body,
			...options
		});
	}
	/**
	* Analyze a company's landing page and web search evidence to return direct
	* competitors for the same product or market.
	*
	* @example
	* ```ts
	* const response = await client.web.extractCompetitors({
	*   domain: 'xxx',
	* });
	* ```
	*/
	extractCompetitors(query, options) {
		return this._client.get("/web/competitors", {
			query,
			...options
		});
	}
	/**
	* Scrape font information from a website including font families, usage
	* statistics, fallbacks, and element/word counts.
	*
	* @example
	* ```ts
	* const response = await client.web.extractFonts();
	* ```
	*/
	extractFonts(query = {}, options) {
		return this._client.get("/web/fonts", {
			query,
			...options
		});
	}
	/**
	* Extract a comprehensive design system from a website including colors,
	* typography, spacing, shadows, and UI components.
	*
	* @example
	* ```ts
	* const response = await client.web.extractStyleguide();
	* ```
	*/
	extractStyleguide(query = {}, options) {
		return this._client.get("/web/styleguide", {
			query,
			...options
		});
	}
	/**
	* Capture a screenshot of a website.
	*
	* @example
	* ```ts
	* const response = await client.web.screenshot();
	* ```
	*/
	screenshot(query = {}, options) {
		return this._client.get("/web/screenshot", {
			query,
			...options
		});
	}
	/**
	* Search the web and optionally scrape each result to Markdown in one round-trip.
	*
	* @example
	* ```ts
	* const response = await client.web.search({ query: 'x' });
	* ```
	*/
	search(body, options) {
		return this._client.post("/web/search", {
			body,
			...options
		});
	}
	/**
	* Performs a crawl starting from a given URL, extracts page content as Markdown,
	* and returns results for all crawled pages.
	*
	* @example
	* ```ts
	* const response = await client.web.webCrawlMd({
	*   url: 'https://example.com',
	* });
	* ```
	*/
	webCrawlMd(body, options) {
		return this._client.post("/web/crawl", {
			body,
			...options
		});
	}
	/**
	* Scrapes the given URL and returns the raw HTML content of the page. The base
	* request costs 1 credit; requests with browser actions cost 2 credits.
	*
	* @example
	* ```ts
	* const response = await client.web.webScrapeHTML({
	*   url: 'https://example.com',
	* });
	* ```
	*/
	webScrapeHTML(query, options) {
		return this._client.get("/web/scrape/html", {
			query,
			...options
		});
	}
	/**
	* Extract image assets from a web page, including standard URLs, inline SVGs, data
	* URIs, responsive image sources, metadata, CSS backgrounds, video posters, and
	* embeds. The base request costs 1 credit, or 2 credits with browser actions. When
	* enrichment is enabled, the entire call costs 5 credits, including requests that
	* also use actions.
	*
	* @example
	* ```ts
	* const response = await client.web.webScrapeImages({
	*   url: 'https://example.com',
	* });
	* ```
	*/
	webScrapeImages(query, options) {
		return this._client.get("/web/scrape/images", {
			query,
			...options
		});
	}
	/**
	* Scrapes the given URL into LLM usable Markdown. Inspect key_metadata on JSON
	* responses from a recognized API key; use error_code to distinguish stable
	* failure categories.
	*
	* ### Billing & errors
	*
	* | HTTP status | Billed?                                   | Meaning                                                                                  |
	* | ----------- | ----------------------------------------- | ---------------------------------------------------------------------------------------- |
	* | 200         | Yes — 1 credit, or 2 credits with actions | Successful scrape, including a zero-length result when includeSelectors matched nothing  |
	* | 400         | No                                        | Invalid input, skipped PDF, or the page could not be scraped                             |
	* | 401 / 403   | No                                        | Invalid/disabled key, insufficient permissions, or credits exhausted; inspect error_code |
	* | 404         | No                                        | Target page returned or fingerprinted as not found                                       |
	* | 408         | No                                        | Request timed out                                                                        |
	* | 415         | No                                        | Unsupported content type                                                                 |
	* | 429         | No                                        | Per-minute rate limit exceeded; honor Retry-After                                        |
	* | 500         | No                                        | Internal error                                                                           |
	*
	* @example
	* ```ts
	* const response = await client.web.webScrapeMd({
	*   url: 'https://example.com',
	* });
	* ```
	*/
	webScrapeMd(query, options) {
		return this._client.get("/web/scrape/markdown", {
			query,
			...options
		});
	}
	/**
	* Crawl an entire website's sitemap and return all discovered page URLs.
	*
	* @example
	* ```ts
	* const response = await client.web.webScrapeSitemap({
	*   domain: 'xxx',
	* });
	* ```
	*/
	webScrapeSitemap(query, options) {
		return this._client.get("/web/scrape/sitemap", {
			query,
			...options
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/log.mjs
const levelNumbers = {
	off: 0,
	error: 200,
	warn: 300,
	info: 400,
	debug: 500
};
const parseLogLevel = (maybeLevel, sourceName, client) => {
	if (!maybeLevel) return;
	if (hasOwn(levelNumbers, maybeLevel)) return maybeLevel;
	loggerFor(client).warn(`${sourceName} was set to ${JSON.stringify(maybeLevel)}, expected one of ${JSON.stringify(Object.keys(levelNumbers))}`);
};
function noop() {}
function makeLogFn(fnLevel, logger, logLevel) {
	if (!logger || levelNumbers[fnLevel] > levelNumbers[logLevel]) return noop;
	else return logger[fnLevel].bind(logger);
}
const noopLogger = {
	error: noop,
	warn: noop,
	info: noop,
	debug: noop
};
let cachedLoggers = /* @__PURE__ */ new WeakMap();
function loggerFor(client) {
	const logger = client.logger;
	const logLevel = client.logLevel ?? "off";
	if (!logger) return noopLogger;
	const cachedLogger = cachedLoggers.get(logger);
	if (cachedLogger && cachedLogger[0] === logLevel) return cachedLogger[1];
	const levelLogger = {
		error: makeLogFn("error", logger, logLevel),
		warn: makeLogFn("warn", logger, logLevel),
		info: makeLogFn("info", logger, logLevel),
		debug: makeLogFn("debug", logger, logLevel)
	};
	cachedLoggers.set(logger, [logLevel, levelLogger]);
	return levelLogger;
}
const formatRequestDetails = (details) => {
	if (details.options) {
		details.options = { ...details.options };
		delete details.options["headers"];
	}
	if (details.headers) details.headers = Object.fromEntries((details.headers instanceof Headers ? [...details.headers] : Object.entries(details.headers)).map(([name, value]) => [name, name.toLowerCase() === "authorization" || name.toLowerCase() === "api-key" || name.toLowerCase() === "x-api-key" || name.toLowerCase() === "cookie" || name.toLowerCase() === "set-cookie" ? "***" : value]));
	if ("retryOfRequestLogID" in details) {
		if (details.retryOfRequestLogID) details.retryOf = details.retryOfRequestLogID;
		delete details.retryOfRequestLogID;
	}
	return details;
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/parse.mjs
async function defaultParseResponse(client, props) {
	const { response, requestLogID, retryOfRequestLogID, startTime } = props;
	const body = await (async () => {
		if (response.status === 204) return null;
		if (props.options.__binaryResponse) return response;
		const mediaType = response.headers.get("content-type")?.split(";")[0]?.trim();
		if (mediaType?.includes("application/json") || mediaType?.endsWith("+json")) {
			if (response.headers.get("content-length") === "0") return;
			return await response.json();
		}
		return await response.text();
	})();
	loggerFor(client).debug(`[${requestLogID}] response parsed`, formatRequestDetails({
		retryOfRequestLogID,
		url: response.url,
		status: response.status,
		body,
		durationMs: Date.now() - startTime
	}));
	return body;
}
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/core/api-promise.mjs
var _APIPromise_client;
/**
* A subclass of `Promise` providing additional helper methods
* for interacting with the SDK.
*/
var APIPromise = class APIPromise extends Promise {
	constructor(client, responsePromise, parseResponse = defaultParseResponse) {
		super((resolve) => {
			resolve(null);
		});
		this.responsePromise = responsePromise;
		this.parseResponse = parseResponse;
		_APIPromise_client.set(this, void 0);
		__classPrivateFieldSet(this, _APIPromise_client, client, "f");
	}
	_thenUnwrap(transform) {
		return new APIPromise(__classPrivateFieldGet(this, _APIPromise_client, "f"), this.responsePromise, async (client, props) => transform(await this.parseResponse(client, props), props));
	}
	/**
	* Gets the raw `Response` instance instead of parsing the response
	* data.
	*
	* If you want to parse the response body but still get the `Response`
	* instance, you can use {@link withResponse()}.
	*
	* 👋 Getting the wrong TypeScript type for `Response`?
	* Try setting `"moduleResolution": "NodeNext"` or add `"lib": ["DOM"]`
	* to your `tsconfig.json`.
	*/
	asResponse() {
		return this.responsePromise.then((p) => p.response);
	}
	/**
	* Gets the parsed response data and the raw `Response` instance.
	*
	* If you just want to get the raw `Response` instance without parsing it,
	* you can use {@link asResponse()}.
	*
	* 👋 Getting the wrong TypeScript type for `Response`?
	* Try setting `"moduleResolution": "NodeNext"` or add `"lib": ["DOM"]`
	* to your `tsconfig.json`.
	*/
	async withResponse() {
		const [data, response] = await Promise.all([this.parse(), this.asResponse()]);
		return {
			data,
			response
		};
	}
	parse() {
		if (!this.parsedPromise) this.parsedPromise = this.responsePromise.then((data) => this.parseResponse(__classPrivateFieldGet(this, _APIPromise_client, "f"), data));
		return this.parsedPromise;
	}
	then(onfulfilled, onrejected) {
		return this.parse().then(onfulfilled, onrejected);
	}
	catch(onrejected) {
		return this.parse().catch(onrejected);
	}
	finally(onfinally) {
		return this.parse().finally(onfinally);
	}
};
_APIPromise_client = /* @__PURE__ */ new WeakMap();
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/internal/utils/env.mjs
/**
* Read an environment variable.
*
* Trims beginning and trailing whitespace.
*
* Will return undefined if the environment variable doesn't exist or cannot be accessed.
*/
const readEnv = (env) => {
	if (typeof globalThis.process !== "undefined") return globalThis.process.env?.[env]?.trim() || void 0;
	if (typeof globalThis.Deno !== "undefined") return globalThis.Deno.env?.get?.(env)?.trim() || void 0;
};
//#endregion
//#region ../../node_modules/.bun/context.dev@2.7.0/node_modules/context.dev/client.mjs
var _ContextDev_instances;
var _a;
var _ContextDev_encoder;
var _ContextDev_baseURLOverridden;
/**
* API Client for interfacing with the Context Dev API.
*/
var ContextDev = class {
	/**
	* API Client for interfacing with the Context Dev API.
	*
	* @param {string | undefined} [opts.apiKey=process.env['CONTEXT_DEV_API_KEY'] ?? undefined]
	* @param {string} [opts.baseURL=process.env['CONTEXT_DEV_BASE_URL'] ?? https://api.context.dev/v1] - Override the default base URL for the API.
	* @param {number} [opts.timeout=1 minute] - The maximum amount of time (in milliseconds) the client will wait for a response before timing out.
	* @param {MergedRequestInit} [opts.fetchOptions] - Additional `RequestInit` options to be passed to `fetch` calls.
	* @param {Fetch} [opts.fetch] - Specify a custom `fetch` function implementation.
	* @param {number} [opts.maxRetries=2] - The maximum number of times the client will retry a request.
	* @param {HeadersLike} opts.defaultHeaders - Default headers to include with every request to the API.
	* @param {Record<string, string | undefined>} opts.defaultQuery - Default query parameters to include with every request to the API.
	*/
	constructor({ baseURL = readEnv("CONTEXT_DEV_BASE_URL"), apiKey = readEnv("CONTEXT_DEV_API_KEY"), ...opts } = {}) {
		_ContextDev_instances.add(this);
		_ContextDev_encoder.set(this, void 0);
		this.parse = new Parse(this);
		this.web = new Web(this);
		this.ai = new AI(this);
		this.brand = new Brand(this);
		this.industry = new Industry(this);
		this.utility = new Utility(this);
		/**
		* Monitor pages, sitemaps, and extracted website data for exact or semantic changes. Webhook payloads are documented by the MonitorsChangeDetectedWebhookPayload and MonitorsRunCompletedWebhookPayload schemas.
		*/
		this.monitors = new Monitors(this);
		this.batch = new Batch(this);
		if (apiKey === void 0) throw new ContextDevError("The CONTEXT_DEV_API_KEY environment variable is missing or empty; either provide it, or instantiate the ContextDev client with an apiKey option, like new ContextDev({ apiKey: 'My API Key' }).");
		const options = {
			apiKey,
			...opts,
			baseURL: baseURL || `https://api.context.dev/v1`
		};
		this.baseURL = options.baseURL;
		this.timeout = options.timeout ?? _a.DEFAULT_TIMEOUT;
		this.logger = options.logger ?? console;
		const defaultLogLevel = "warn";
		this.logLevel = defaultLogLevel;
		this.logLevel = parseLogLevel(options.logLevel, "ClientOptions.logLevel", this) ?? parseLogLevel(readEnv("CONTEXT_DEV_LOG"), "process.env['CONTEXT_DEV_LOG']", this) ?? defaultLogLevel;
		this.fetchOptions = options.fetchOptions;
		this.maxRetries = options.maxRetries ?? 2;
		this.fetch = options.fetch ?? getDefaultFetch();
		__classPrivateFieldSet(this, _ContextDev_encoder, FallbackEncoder, "f");
		const customHeadersEnv = readEnv("CONTEXT_DEV_CUSTOM_HEADERS");
		if (customHeadersEnv) {
			const parsed = {};
			for (const line of customHeadersEnv.split("\n")) {
				const colon = line.indexOf(":");
				if (colon >= 0) parsed[line.substring(0, colon).trim()] = line.substring(colon + 1).trim();
			}
			options.defaultHeaders = {
				...parsed,
				...options.defaultHeaders
			};
		}
		this._options = options;
		this.apiKey = apiKey;
	}
	/**
	* Create a new client instance re-using the same options given to the current client with optional overriding.
	*/
	withOptions(options) {
		return new this.constructor({
			...this._options,
			baseURL: this.baseURL,
			maxRetries: this.maxRetries,
			timeout: this.timeout,
			logger: this.logger,
			logLevel: this.logLevel,
			fetch: this.fetch,
			fetchOptions: this.fetchOptions,
			apiKey: this.apiKey,
			...options
		});
	}
	defaultQuery() {
		return this._options.defaultQuery;
	}
	validateHeaders({ values, nulls }) {}
	async authHeaders(opts) {
		return buildHeaders([{ Authorization: `Bearer ${this.apiKey}` }]);
	}
	stringifyQuery(query) {
		return stringifyQuery(query);
	}
	getUserAgent() {
		return `${this.constructor.name}/JS 2.7.0`;
	}
	defaultIdempotencyKey() {
		return `stainless-node-retry-${uuid4()}`;
	}
	makeStatusError(status, error, message, headers) {
		return APIError.generate(status, error, message, headers);
	}
	buildURL(path, query, defaultBaseURL) {
		const baseURL = !__classPrivateFieldGet(this, _ContextDev_instances, "m", _ContextDev_baseURLOverridden).call(this) && defaultBaseURL || this.baseURL;
		const url = isAbsoluteURL(path) ? new URL(path) : new URL(baseURL + (baseURL.endsWith("/") && path.startsWith("/") ? path.slice(1) : path));
		const defaultQuery = this.defaultQuery();
		const pathQuery = Object.fromEntries(url.searchParams);
		if (!isEmptyObj(defaultQuery) || !isEmptyObj(pathQuery)) query = {
			...pathQuery,
			...defaultQuery,
			...query
		};
		if (typeof query === "object" && query && !Array.isArray(query)) url.search = this.stringifyQuery(query);
		return url.toString();
	}
	/**
	* Used as a callback for mutating the given `FinalRequestOptions` object.
	*/
	async prepareOptions(options) {}
	/**
	* Used as a callback for mutating the given `RequestInit` object.
	*
	* This is useful for cases where you want to add certain headers based off of
	* the request properties, e.g. `method` or `url`.
	*/
	async prepareRequest(request, { url, options }) {}
	get(path, opts) {
		return this.methodRequest("get", path, opts);
	}
	post(path, opts) {
		return this.methodRequest("post", path, opts);
	}
	patch(path, opts) {
		return this.methodRequest("patch", path, opts);
	}
	put(path, opts) {
		return this.methodRequest("put", path, opts);
	}
	delete(path, opts) {
		return this.methodRequest("delete", path, opts);
	}
	methodRequest(method, path, opts) {
		return this.request(Promise.resolve(opts).then((opts) => {
			return {
				method,
				path,
				...opts
			};
		}));
	}
	request(options, remainingRetries = null) {
		return new APIPromise(this, this.makeRequest(options, remainingRetries, void 0));
	}
	async makeRequest(optionsInput, retriesRemaining, retryOfRequestLogID) {
		const options = await optionsInput;
		const maxRetries = options.maxRetries ?? this.maxRetries;
		if (retriesRemaining == null) retriesRemaining = maxRetries;
		await this.prepareOptions(options);
		const { req, url, timeout } = await this.buildRequest(options, { retryCount: maxRetries - retriesRemaining });
		await this.prepareRequest(req, {
			url,
			options
		});
		/** Not an API request ID, just for correlating local log entries. */
		const requestLogID = "log_" + (Math.random() * (1 << 24) | 0).toString(16).padStart(6, "0");
		const retryLogStr = retryOfRequestLogID === void 0 ? "" : `, retryOf: ${retryOfRequestLogID}`;
		const startTime = Date.now();
		loggerFor(this).debug(`[${requestLogID}] sending request`, formatRequestDetails({
			retryOfRequestLogID,
			method: options.method,
			url,
			options,
			headers: req.headers
		}));
		if (options.signal?.aborted) throw new APIUserAbortError();
		const controller = new AbortController();
		const response = await this.fetchWithTimeout(url, req, timeout, controller).catch(castToError);
		const headersTime = Date.now();
		if (response instanceof globalThis.Error) {
			const retryMessage = `retrying, ${retriesRemaining} attempts remaining`;
			if (options.signal?.aborted) throw new APIUserAbortError();
			const isTimeout = isAbortError(response) || /timed? ?out/i.test(String(response) + ("cause" in response ? String(response.cause) : ""));
			if (retriesRemaining) {
				loggerFor(this).info(`[${requestLogID}] connection ${isTimeout ? "timed out" : "failed"} - ${retryMessage}`);
				loggerFor(this).debug(`[${requestLogID}] connection ${isTimeout ? "timed out" : "failed"} (${retryMessage})`, formatRequestDetails({
					retryOfRequestLogID,
					url,
					durationMs: headersTime - startTime,
					message: response.message
				}));
				return this.retryRequest(options, retriesRemaining, retryOfRequestLogID ?? requestLogID);
			}
			loggerFor(this).info(`[${requestLogID}] connection ${isTimeout ? "timed out" : "failed"} - error; no more retries left`);
			loggerFor(this).debug(`[${requestLogID}] connection ${isTimeout ? "timed out" : "failed"} (error; no more retries left)`, formatRequestDetails({
				retryOfRequestLogID,
				url,
				durationMs: headersTime - startTime,
				message: response.message
			}));
			if (isTimeout) throw new APIConnectionTimeoutError();
			throw new APIConnectionError({ cause: response });
		}
		const responseInfo = `[${requestLogID}${retryLogStr}] ${req.method} ${url} ${response.ok ? "succeeded" : "failed"} with status ${response.status} in ${headersTime - startTime}ms`;
		if (!response.ok) {
			const shouldRetry = await this.shouldRetry(response);
			if (retriesRemaining && shouldRetry) {
				const retryMessage = `retrying, ${retriesRemaining} attempts remaining`;
				await CancelReadableStream(response.body);
				loggerFor(this).info(`${responseInfo} - ${retryMessage}`);
				loggerFor(this).debug(`[${requestLogID}] response error (${retryMessage})`, formatRequestDetails({
					retryOfRequestLogID,
					url: response.url,
					status: response.status,
					headers: response.headers,
					durationMs: headersTime - startTime
				}));
				return this.retryRequest(options, retriesRemaining, retryOfRequestLogID ?? requestLogID, response.headers);
			}
			const retryMessage = shouldRetry ? `error; no more retries left` : `error; not retryable`;
			loggerFor(this).info(`${responseInfo} - ${retryMessage}`);
			const errText = await response.text().catch((err) => castToError(err).message);
			const errJSON = safeJSON(errText);
			const errMessage = errJSON ? void 0 : errText;
			loggerFor(this).debug(`[${requestLogID}] response error (${retryMessage})`, formatRequestDetails({
				retryOfRequestLogID,
				url: response.url,
				status: response.status,
				headers: response.headers,
				message: errMessage,
				durationMs: Date.now() - startTime
			}));
			throw this.makeStatusError(response.status, errJSON, errMessage, response.headers);
		}
		loggerFor(this).info(responseInfo);
		loggerFor(this).debug(`[${requestLogID}] response start`, formatRequestDetails({
			retryOfRequestLogID,
			url: response.url,
			status: response.status,
			headers: response.headers,
			durationMs: headersTime - startTime
		}));
		return {
			response,
			options,
			controller,
			requestLogID,
			retryOfRequestLogID,
			startTime
		};
	}
	async fetchWithTimeout(url, init, ms, controller) {
		const { signal, method, ...options } = init || {};
		const abort = this._makeAbort(controller);
		if (signal) signal.addEventListener("abort", abort, { once: true });
		const timeout = setTimeout(abort, ms);
		const isReadableBody = globalThis.ReadableStream && options.body instanceof globalThis.ReadableStream || typeof options.body === "object" && options.body !== null && Symbol.asyncIterator in options.body;
		const fetchOptions = {
			signal: controller.signal,
			...isReadableBody ? { duplex: "half" } : {},
			method: "GET",
			...options
		};
		if (method) fetchOptions.method = method.toUpperCase();
		try {
			return await this.fetch.call(void 0, url, fetchOptions);
		} finally {
			clearTimeout(timeout);
		}
	}
	async shouldRetry(response) {
		const shouldRetryHeader = response.headers.get("x-should-retry");
		if (shouldRetryHeader === "true") return true;
		if (shouldRetryHeader === "false") return false;
		if (response.status === 408) return true;
		if (response.status === 409) return true;
		if (response.status === 429) return true;
		if (response.status >= 500) return true;
		return false;
	}
	async retryRequest(options, retriesRemaining, requestLogID, responseHeaders) {
		let timeoutMillis;
		const retryAfterMillisHeader = responseHeaders?.get("retry-after-ms");
		if (retryAfterMillisHeader) {
			const timeoutMs = parseFloat(retryAfterMillisHeader);
			if (!Number.isNaN(timeoutMs)) timeoutMillis = timeoutMs;
		}
		const retryAfterHeader = responseHeaders?.get("retry-after");
		if (retryAfterHeader && !timeoutMillis) {
			const timeoutSeconds = parseFloat(retryAfterHeader);
			if (!Number.isNaN(timeoutSeconds)) timeoutMillis = timeoutSeconds * 1e3;
			else timeoutMillis = Date.parse(retryAfterHeader) - Date.now();
		}
		if (timeoutMillis === void 0) {
			const maxRetries = options.maxRetries ?? this.maxRetries;
			timeoutMillis = this.calculateDefaultRetryTimeoutMillis(retriesRemaining, maxRetries);
		}
		await sleep(timeoutMillis);
		return this.makeRequest(options, retriesRemaining - 1, requestLogID);
	}
	calculateDefaultRetryTimeoutMillis(retriesRemaining, maxRetries) {
		const initialRetryDelay = .5;
		const maxRetryDelay = 8;
		const numRetries = maxRetries - retriesRemaining;
		return Math.min(initialRetryDelay * Math.pow(2, numRetries), maxRetryDelay) * (1 - Math.random() * .25) * 1e3;
	}
	async buildRequest(inputOptions, { retryCount = 0 } = {}) {
		const options = { ...inputOptions };
		const { method, path, query, defaultBaseURL } = options;
		const url = this.buildURL(path, query, defaultBaseURL);
		if ("timeout" in options) validatePositiveInteger("timeout", options.timeout);
		options.timeout = options.timeout ?? this.timeout;
		const { bodyHeaders, body } = this.buildBody({ options });
		return {
			req: {
				method,
				headers: await this.buildHeaders({
					options: inputOptions,
					method,
					bodyHeaders,
					retryCount
				}),
				...options.signal && { signal: options.signal },
				...globalThis.ReadableStream && body instanceof globalThis.ReadableStream && { duplex: "half" },
				...body && { body },
				...this.fetchOptions ?? {},
				...options.fetchOptions ?? {}
			},
			url,
			timeout: options.timeout
		};
	}
	async buildHeaders({ options, method, bodyHeaders, retryCount }) {
		let idempotencyHeaders = {};
		if (this.idempotencyHeader && method !== "get") {
			if (!options.idempotencyKey) options.idempotencyKey = this.defaultIdempotencyKey();
			idempotencyHeaders[this.idempotencyHeader] = options.idempotencyKey;
		}
		const headers = buildHeaders([
			idempotencyHeaders,
			{
				Accept: "application/json",
				"User-Agent": this.getUserAgent(),
				"X-Stainless-Retry-Count": String(retryCount),
				...options.timeout ? { "X-Stainless-Timeout": String(Math.trunc(options.timeout / 1e3)) } : {},
				...getPlatformHeaders()
			},
			await this.authHeaders(options),
			this._options.defaultHeaders,
			bodyHeaders,
			options.headers
		]);
		this.validateHeaders(headers);
		return headers.values;
	}
	_makeAbort(controller) {
		return () => controller.abort();
	}
	buildBody({ options }) {
		const { body, headers: rawHeaders } = options;
		if (!body) {
			if (body == null && "body" in options) return __classPrivateFieldGet(this, _ContextDev_encoder, "f").call(this, {
				body,
				headers: buildHeaders([rawHeaders])
			});
			return {
				bodyHeaders: void 0,
				body: void 0
			};
		}
		const headers = buildHeaders([rawHeaders]);
		if (ArrayBuffer.isView(body) || body instanceof ArrayBuffer || body instanceof DataView || typeof body === "string" && headers.values.has("content-type") || globalThis.Blob && body instanceof globalThis.Blob || body instanceof FormData || body instanceof URLSearchParams || globalThis.ReadableStream && body instanceof globalThis.ReadableStream) return {
			bodyHeaders: void 0,
			body
		};
		else if (typeof body === "object" && (Symbol.asyncIterator in body || Symbol.iterator in body && "next" in body && typeof body.next === "function")) return {
			bodyHeaders: void 0,
			body: ReadableStreamFrom(body)
		};
		else if (typeof body === "object" && headers.values.get("content-type") === "application/x-www-form-urlencoded") return {
			bodyHeaders: { "content-type": "application/x-www-form-urlencoded" },
			body: this.stringifyQuery(body)
		};
		else return __classPrivateFieldGet(this, _ContextDev_encoder, "f").call(this, {
			body,
			headers
		});
	}
};
_a = ContextDev, _ContextDev_encoder = /* @__PURE__ */ new WeakMap(), _ContextDev_instances = /* @__PURE__ */ new WeakSet(), _ContextDev_baseURLOverridden = function _ContextDev_baseURLOverridden() {
	return this.baseURL !== "https://api.context.dev/v1";
};
ContextDev.ContextDev = _a;
ContextDev.DEFAULT_TIMEOUT = 6e4;
ContextDev.ContextDevError = ContextDevError;
ContextDev.APIError = APIError;
ContextDev.APIConnectionError = APIConnectionError;
ContextDev.APIConnectionTimeoutError = APIConnectionTimeoutError;
ContextDev.APIUserAbortError = APIUserAbortError;
ContextDev.NotFoundError = NotFoundError;
ContextDev.ConflictError = ConflictError;
ContextDev.RateLimitError = RateLimitError;
ContextDev.BadRequestError = BadRequestError;
ContextDev.AuthenticationError = AuthenticationError;
ContextDev.InternalServerError = InternalServerError;
ContextDev.PermissionDeniedError = PermissionDeniedError;
ContextDev.UnprocessableEntityError = UnprocessableEntityError;
ContextDev.toFile = toFile;
ContextDev.Parse = Parse;
ContextDev.Web = Web;
ContextDev.AI = AI;
ContextDev.Brand = Brand;
ContextDev.Industry = Industry;
ContextDev.Utility = Utility;
ContextDev.Monitors = Monitors;
ContextDev.Batch = Batch;
//#endregion
export { APIError as n, ContextDev as t };
