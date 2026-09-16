import { fileURLToPath as __eveFileURLToPath } from "node:url";
import { dirname as __eveDirname } from "node:path";
const __filename = __eveFileURLToPath(import.meta.url);
__eveDirname(__filename);
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/featureFlagUtils.mjs
const normalizeFlagsResponse = (flagsResponse) => {
	if ("flags" in flagsResponse) {
		const featureFlags = getFlagValuesFromFlags(flagsResponse.flags);
		const featureFlagPayloads = getPayloadsFromFlags(flagsResponse.flags);
		return {
			...flagsResponse,
			featureFlags,
			featureFlagPayloads
		};
	}
	{
		const featureFlags = flagsResponse.featureFlags ?? {};
		const featureFlagPayloads = Object.fromEntries(Object.entries(flagsResponse.featureFlagPayloads || {}).map(([k, v]) => [k, parsePayload(v)]));
		const flags = Object.fromEntries(Object.entries(featureFlags).map(([key, value]) => [key, getFlagDetailFromFlagAndPayload(key, value, featureFlagPayloads[key])]));
		return {
			...flagsResponse,
			featureFlags,
			featureFlagPayloads,
			flags
		};
	}
};
function getFlagDetailFromFlagAndPayload(key, value, payload) {
	return {
		key,
		enabled: "string" == typeof value ? true : value,
		variant: "string" == typeof value ? value : void 0,
		reason: void 0,
		metadata: {
			id: void 0,
			version: void 0,
			payload: payload ? JSON.stringify(payload) : void 0,
			description: void 0
		}
	};
}
const getFlagValuesFromFlags = (flags) => Object.fromEntries(Object.entries(flags ?? {}).map(([key, detail]) => [key, getFeatureFlagValue(detail)]).filter(([, value]) => void 0 !== value));
const getPayloadsFromFlags = (flags) => {
	const safeFlags = flags ?? {};
	return Object.fromEntries(Object.keys(safeFlags).filter((flag) => {
		const details = safeFlags[flag];
		return details.enabled && details.metadata && void 0 !== details.metadata.payload;
	}).map((flag) => {
		const payload = safeFlags[flag].metadata?.payload;
		return [flag, payload ? parsePayload(payload) : void 0];
	}));
};
const getFeatureFlagValue = (detail) => void 0 === detail ? void 0 : detail.variant ?? detail.enabled;
const parsePayload = (response) => {
	if ("string" != typeof response) return response;
	try {
		return JSON.parse(response);
	} catch {
		return response;
	}
};
const MINIMAL_FLAG_CALLED_EVENT_PROPERTIES = [
	"$feature_flag",
	"$feature_flag_response",
	"$feature_flag_has_experiment",
	"$feature_flag_id",
	"$feature_flag_version",
	"$feature_flag_reason",
	"$feature_flag_request_id",
	"$feature_flag_evaluated_at",
	"$feature_flag_error",
	"locally_evaluated",
	"$groups",
	"$process_person_profile",
	"$geoip_disable",
	"$current_url",
	"$pathname",
	"$referring_domain",
	...[
		"utm_source",
		"utm_medium",
		"utm_campaign",
		"utm_content",
		"utm_term",
		"gad_source",
		"mc_cid",
		"gclid",
		"gclsrc",
		"dclid",
		"gbraid",
		"wbraid",
		"fbclid",
		"msclkid",
		"twclid",
		"li_fat_id",
		"igshid",
		"ttclid",
		"rdt_cid",
		"epik",
		"qclid",
		"sccid",
		"irclid",
		"_kx"
	],
	"$session_id",
	"$window_id",
	"$lib",
	"$lib_version",
	"$device_id",
	"$is_server"
];
const minimizeFlagCalledEventProperties = (properties, transportKeys = []) => {
	const minimal = {};
	const copyKey = (key) => {
		if (void 0 !== properties[key]) minimal[key] = properties[key];
	};
	MINIMAL_FLAG_CALLED_EVENT_PROPERTIES.forEach(copyKey);
	transportKeys.forEach(copyKey);
	return minimal;
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/types.mjs
var types_PostHogPersistedProperty = /*#__PURE__*/ function(PostHogPersistedProperty) {
	PostHogPersistedProperty["AnonymousId"] = "anonymous_id";
	PostHogPersistedProperty["DistinctId"] = "distinct_id";
	PostHogPersistedProperty["Props"] = "props";
	PostHogPersistedProperty["EnablePersonProcessing"] = "enable_person_processing";
	PostHogPersistedProperty["PersonMode"] = "person_mode";
	PostHogPersistedProperty["FeatureFlagDetails"] = "feature_flag_details";
	PostHogPersistedProperty["FeatureFlags"] = "feature_flags";
	PostHogPersistedProperty["FeatureFlagPayloads"] = "feature_flag_payloads";
	PostHogPersistedProperty["BootstrapFeatureFlagDetails"] = "bootstrap_feature_flag_details";
	PostHogPersistedProperty["BootstrapFeatureFlags"] = "bootstrap_feature_flags";
	PostHogPersistedProperty["BootstrapFeatureFlagPayloads"] = "bootstrap_feature_flag_payloads";
	PostHogPersistedProperty["OverrideFeatureFlags"] = "override_feature_flags";
	PostHogPersistedProperty["Queue"] = "queue";
	PostHogPersistedProperty["AiQueue"] = "ai_queue";
	PostHogPersistedProperty["LogsQueue"] = "logs_queue";
	PostHogPersistedProperty["OptedOut"] = "opted_out";
	PostHogPersistedProperty["SessionId"] = "session_id";
	PostHogPersistedProperty["SessionStartTimestamp"] = "session_start_timestamp";
	PostHogPersistedProperty["SessionLastTimestamp"] = "session_timestamp";
	PostHogPersistedProperty["PersonProperties"] = "person_properties";
	PostHogPersistedProperty["GroupProperties"] = "group_properties";
	PostHogPersistedProperty["InstalledAppBuild"] = "installed_app_build";
	PostHogPersistedProperty["InstalledAppVersion"] = "installed_app_version";
	PostHogPersistedProperty["SessionReplay"] = "session_replay";
	PostHogPersistedProperty["SessionReplayEventTriggerActivatedSession"] = "session_replay_event_trigger_activated_session";
	PostHogPersistedProperty["SurveyLastSeenDate"] = "survey_last_seen_date";
	PostHogPersistedProperty["SurveysSeen"] = "surveys_seen";
	PostHogPersistedProperty["Surveys"] = "surveys";
	PostHogPersistedProperty["RemoteConfig"] = "remote_config";
	PostHogPersistedProperty["FlagsEndpointWasHit"] = "flags_endpoint_was_hit";
	PostHogPersistedProperty["DeviceId"] = "device_id";
	return PostHogPersistedProperty;
}({});
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/gzip.mjs
function isGzipSupported() {
	return "CompressionStream" in globalThis && "TextEncoder" in globalThis && "Response" in globalThis && "function" == typeof Response.prototype.blob;
}
const NATIVE_GZIP_VALIDATION_ERROR = "NativeGzipValidationError";
const GZIP_MAGIC_FIRST_BYTE = 31;
const GZIP_MAGIC_SECOND_BYTE = 139;
const GZIP_DEFLATE_METHOD = 8;
const hasGzipMagic = (bytes) => bytes.length >= 2 && bytes[0] === GZIP_MAGIC_FIRST_BYTE && bytes[1] === GZIP_MAGIC_SECOND_BYTE;
let crc32Table;
const getCrc32Table = () => {
	if (crc32Table) return crc32Table;
	crc32Table = [];
	for (let i = 0; i < 256; i++) {
		let crc = i;
		for (let j = 0; j < 8; j++) crc = 1 & crc ? 3988292384 ^ crc >>> 1 : crc >>> 1;
		crc32Table[i] = crc >>> 0;
	}
	return crc32Table;
};
const crc32 = (bytes) => {
	const table = getCrc32Table();
	let crc = 4294967295;
	for (let i = 0; i < bytes.length; i++) crc = table[(crc ^ bytes[i]) & 255] ^ crc >>> 8;
	return (4294967295 ^ crc) >>> 0;
};
const throwNativeGzipValidationError = (reason) => {
	const error = /* @__PURE__ */ new Error(`Native gzip produced invalid output: ${reason}`);
	error.name = NATIVE_GZIP_VALIDATION_ERROR;
	throw error;
};
const validateNativeGzip = async (compressed, inputBytes) => {
	if (compressed.size < 18) throwNativeGzipValidationError("too-short");
	const header = new Uint8Array(await compressed.slice(0, 10).arrayBuffer());
	if (!hasGzipMagic(header) || header[2] !== GZIP_DEFLATE_METHOD) throwNativeGzipValidationError("invalid-header");
	const trailer = new DataView(await compressed.slice(compressed.size - 8).arrayBuffer());
	if (trailer.getUint32(0, true) !== crc32(inputBytes)) throwNativeGzipValidationError("invalid-crc");
	const inputSize = inputBytes.length >>> 0;
	if (trailer.getUint32(4, true) !== inputSize) throwNativeGzipValidationError("invalid-size");
};
async function gzipCompress(input, isDebug = true, options) {
	try {
		const inputBytes = new TextEncoder().encode(input);
		const compressedStream = new globalThis.CompressionStream("gzip");
		const writer = compressedStream.writable.getWriter();
		const writePromise = writer.write(inputBytes).then(() => writer.close()).catch(async (err) => {
			try {
				await writer.abort(err);
			} catch {}
			throw err;
		});
		const responsePromise = new Response(compressedStream.readable).blob();
		const [compressed] = await Promise.all([responsePromise, writePromise]);
		await validateNativeGzip(compressed, inputBytes);
		return compressed;
	} catch (error) {
		if (options?.rethrow) throw error;
		if (isDebug) console.error("Failed to gzip compress data", error);
		return null;
	}
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/bot-detection.mjs
const DEFAULT_BLOCKED_UA_STRS = [
	"amazonbot",
	"amazonproductbot",
	"app.hypefactors.com",
	"applebot",
	"archive.org_bot",
	"awariobot",
	"backlinksextendedbot",
	"baiduspider",
	"bingbot",
	"bingpreview",
	"chrome-lighthouse",
	"dataforseobot",
	"deepscan",
	"duckduckbot",
	"facebookexternal",
	"facebookcatalog",
	"http://yandex.com/bots",
	"hubspot",
	"ia_archiver",
	"leikibot",
	"linkedinbot",
	"meta-externalagent",
	"mj12bot",
	"msnbot",
	"nessus",
	"petalbot",
	"pinterest",
	"prerender",
	"rogerbot",
	"screaming frog",
	"sebot-wa",
	"sitebulb",
	"slackbot",
	"slurp",
	"trendictionbot",
	"turnitin",
	"twitterbot",
	"vercel-screenshot",
	"vercelbot",
	"yahoo! slurp",
	"yandexbot",
	"zoombot",
	"bot.htm",
	"bot.php",
	"(bot;",
	"bot/",
	"crawler",
	"ahrefsbot",
	"ahrefssiteaudit",
	"semrushbot",
	"siteauditbot",
	"splitsignalbot",
	"gptbot",
	"oai-searchbot",
	"chatgpt-user",
	"perplexitybot",
	"better uptime bot",
	"sentryuptimebot",
	"uptimerobot",
	"headlesschrome",
	"cypress",
	"google-hoteladsverifier",
	"adsbot-google",
	"apis-google",
	"duplexweb-google",
	"feedfetcher-google",
	"google favicon",
	"google web preview",
	"google-read-aloud",
	"googlebot",
	"googleother",
	"google-cloudvertexbot",
	"googleweblight",
	"mediapartners-google",
	"storebot-google",
	"google-inspectiontool",
	"bytespider"
];
const isBlockedUA = function(ua, customBlockedUserAgents = []) {
	if (!ua) return false;
	const uaLower = ua.toLowerCase();
	return DEFAULT_BLOCKED_UA_STRS.concat(customBlockedUserAgents).some((blockedUA) => {
		const blockedUaLower = blockedUA.toLowerCase();
		return -1 !== uaLower.indexOf(blockedUaLower);
	});
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/string-utils.mjs
function safeJsonStringify(value) {
	const ancestors = [];
	return JSON.stringify(value, function(_key, replacementValue) {
		if ("bigint" == typeof replacementValue) return replacementValue.toString();
		if ("function" == typeof replacementValue || "symbol" == typeof replacementValue) return;
		if (replacementValue instanceof Error) return {
			name: replacementValue.name,
			message: replacementValue.message,
			stack: replacementValue.stack
		};
		if (replacementValue && "object" == typeof replacementValue) {
			while (ancestors.length > 0 && ancestors[ancestors.length - 1] !== this) ancestors.pop();
			if (ancestors.includes(replacementValue)) return "[Circular]";
			ancestors.push(replacementValue);
		}
		return replacementValue;
	}) ?? "null";
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/type-utils.mjs
const nativeIsArray = Array.isArray;
const ObjProto = Object.prototype;
ObjProto.hasOwnProperty;
const type_utils_toString = ObjProto.toString;
const isArray = nativeIsArray || function(obj) {
	return "[object Array]" === type_utils_toString.call(obj);
};
const isObject = (x) => x === Object(x) && !isArray(x);
const isUndefined = (x) => void 0 === x;
const isString = (x) => "[object String]" == type_utils_toString.call(x);
const isEmptyString = (x) => isString(x) && 0 === x.trim().length;
const isNull = (x) => null === x;
const isNumber = (x) => "[object Number]" == type_utils_toString.call(x) && x === x;
const isBoolean = (x) => "[object Boolean]" === type_utils_toString.call(x);
function isPrimitive(value) {
	return null === value || "object" != typeof value;
}
function isBuiltin(candidate, className) {
	return Object.prototype.toString.call(candidate) === `[object ${className}]`;
}
function isError$1(candidate) {
	switch (Object.prototype.toString.call(candidate)) {
		case "[object Error]":
		case "[object Exception]":
		case "[object DOMException]":
		case "[object DOMError]":
		case "[object WebAssembly.Exception]": return true;
		default: return isInstanceOf(candidate, Error);
	}
}
function isEvent(candidate) {
	return "undefined" != typeof Event && isInstanceOf(candidate, Event);
}
function isPlainObject(candidate) {
	return isBuiltin(candidate, "Object");
}
function isInstanceOf(candidate, base) {
	try {
		return candidate instanceof base;
	} catch {
		return false;
	}
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/number-utils.mjs
function clampToRange(value, min, max, logger, fallbackValue) {
	if (min > max) {
		logger.warn("min cannot be greater than max.");
		min = max;
	}
	if (isNumber(value)) if (value > max) {
		logger.warn(" cannot be  greater than max: " + max + ". Using max value instead.");
		return max;
	} else {
		if (!(value < min)) return value;
		logger.warn(" cannot be less than min: " + min + ". Using min value instead.");
		return min;
	}
	logger.warn(" must be a number. using max or fallback. max: " + max + ", fallback: " + fallbackValue);
	return clampToRange(fallbackValue || max, min, max, logger);
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/bucketed-rate-limiter.mjs
const ONE_DAY_IN_MS = 864e5;
function resolveExceptionRateLimiterConfig(config = {}) {
	return {
		refillRate: config.exceptionRateLimiterRefillRate ?? config.__exceptionRateLimiterRefillRate ?? 1,
		bucketSize: config.exceptionRateLimiterBucketSize ?? config.__exceptionRateLimiterBucketSize ?? 10
	};
}
var BucketedRateLimiter = class {
	constructor(options) {
		this._buckets = {};
		this._onBucketRateLimited = options._onBucketRateLimited;
		this._bucketSize = clampToRange(options.bucketSize, 0, 100, options._logger);
		this._refillRate = clampToRange(options.refillRate, 0, this._bucketSize, options._logger);
		this._refillInterval = clampToRange(options.refillInterval, 0, ONE_DAY_IN_MS, options._logger);
	}
	_applyRefill(bucket, now) {
		const elapsedMs = now - bucket.lastAccess;
		const refillIntervals = Math.floor(elapsedMs / this._refillInterval);
		if (refillIntervals > 0) {
			const tokensToAdd = refillIntervals * this._refillRate;
			bucket.tokens = Math.min(bucket.tokens + tokensToAdd, this._bucketSize);
			bucket.lastAccess = bucket.lastAccess + refillIntervals * this._refillInterval;
		}
	}
	consumeRateLimit(key) {
		const now = Date.now();
		const keyStr = String(key);
		let bucket = this._buckets[keyStr];
		if (bucket) this._applyRefill(bucket, now);
		else {
			bucket = {
				tokens: this._bucketSize,
				lastAccess: now
			};
			this._buckets[keyStr] = bucket;
		}
		if (0 === bucket.tokens) return true;
		bucket.tokens--;
		if (0 === bucket.tokens) this._onBucketRateLimited?.(key);
		return 0 === bucket.tokens;
	}
	stop() {
		this._buckets = {};
	}
};
Date.prototype.getTime;
Date.prototype.toISOString;
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/vendor/uuidv7.mjs
/*! For license information please see uuidv7.mjs.LICENSE.txt */
/**
* uuidv7: An experimental implementation of the proposed UUID Version 7
*
* @license Apache-2.0
* @copyright 2021-2023 LiosK
* @packageDocumentation
*/ const DIGITS = "0123456789abcdef";
var UUID = class UUID {
	constructor(bytes) {
		this.bytes = bytes;
	}
	static ofInner(bytes) {
		if (16 === bytes.length) return new UUID(bytes);
		throw new TypeError("not 128-bit length");
	}
	static fromFieldsV7(unixTsMs, randA, randBHi, randBLo) {
		if (!Number.isInteger(unixTsMs) || !Number.isInteger(randA) || !Number.isInteger(randBHi) || !Number.isInteger(randBLo) || unixTsMs < 0 || randA < 0 || randBHi < 0 || randBLo < 0 || unixTsMs > 0xffffffffffff || randA > 4095 || randBHi > 1073741823 || randBLo > 4294967295) throw new RangeError("invalid field value");
		const bytes = /* @__PURE__ */ new Uint8Array(16);
		bytes[0] = unixTsMs / 2 ** 40;
		bytes[1] = unixTsMs / 2 ** 32;
		bytes[2] = unixTsMs / 2 ** 24;
		bytes[3] = unixTsMs / 2 ** 16;
		bytes[4] = unixTsMs / 256;
		bytes[5] = unixTsMs;
		bytes[6] = 112 | randA >>> 8;
		bytes[7] = randA;
		bytes[8] = 128 | randBHi >>> 24;
		bytes[9] = randBHi >>> 16;
		bytes[10] = randBHi >>> 8;
		bytes[11] = randBHi;
		bytes[12] = randBLo >>> 24;
		bytes[13] = randBLo >>> 16;
		bytes[14] = randBLo >>> 8;
		bytes[15] = randBLo;
		return new UUID(bytes);
	}
	static parse(uuid) {
		let hex;
		switch (uuid.length) {
			case 32:
				hex = /^[0-9a-f]{32}$/i.exec(uuid)?.[0];
				break;
			case 36:
				hex = /^([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})$/i.exec(uuid)?.slice(1, 6).join("");
				break;
			case 38:
				hex = /^\{([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})\}$/i.exec(uuid)?.slice(1, 6).join("");
				break;
			case 45: hex = /^urn:uuid:([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})$/i.exec(uuid)?.slice(1, 6).join("");
		}
		if (hex) {
			const inner = /* @__PURE__ */ new Uint8Array(16);
			for (let i = 0; i < 16; i += 4) {
				const n = parseInt(hex.substring(2 * i, 2 * i + 8), 16);
				inner[i + 0] = n >>> 24;
				inner[i + 1] = n >>> 16;
				inner[i + 2] = n >>> 8;
				inner[i + 3] = n;
			}
			return new UUID(inner);
		}
		throw new SyntaxError("could not parse UUID string");
	}
	toString() {
		let text = "";
		for (let i = 0; i < this.bytes.length; i++) {
			text += DIGITS.charAt(this.bytes[i] >>> 4);
			text += DIGITS.charAt(15 & this.bytes[i]);
			if (3 === i || 5 === i || 7 === i || 9 === i) text += "-";
		}
		return text;
	}
	toHex() {
		let text = "";
		for (let i = 0; i < this.bytes.length; i++) {
			text += DIGITS.charAt(this.bytes[i] >>> 4);
			text += DIGITS.charAt(15 & this.bytes[i]);
		}
		return text;
	}
	toJSON() {
		return this.toString();
	}
	getVariant() {
		const n = this.bytes[8] >>> 4;
		if (n < 0) throw new Error("unreachable");
		if (n <= 7) return this.bytes.every((e) => 0 === e) ? "NIL" : "VAR_0";
		if (n <= 11) return "VAR_10";
		if (n <= 13) return "VAR_110";
		if (n <= 15) return this.bytes.every((e) => 255 === e) ? "MAX" : "VAR_RESERVED";
		else throw new Error("unreachable");
	}
	getVersion() {
		return "VAR_10" === this.getVariant() ? this.bytes[6] >>> 4 : void 0;
	}
	clone() {
		return new UUID(this.bytes.slice(0));
	}
	equals(other) {
		return 0 === this.compareTo(other);
	}
	compareTo(other) {
		for (let i = 0; i < 16; i++) {
			const diff = this.bytes[i] - other.bytes[i];
			if (0 !== diff) return Math.sign(diff);
		}
		return 0;
	}
};
var V7Generator = class {
	constructor(randomNumberGenerator) {
		this.timestamp = 0;
		this.counter = 0;
		this.random = randomNumberGenerator ?? getDefaultRandom();
	}
	generate() {
		return this.generateOrResetCore(Date.now(), 1e4);
	}
	generateOrAbort() {
		return this.generateOrAbortCore(Date.now(), 1e4);
	}
	generateOrResetCore(unixTsMs, rollbackAllowance) {
		let value = this.generateOrAbortCore(unixTsMs, rollbackAllowance);
		if (void 0 === value) {
			this.timestamp = 0;
			value = this.generateOrAbortCore(unixTsMs, rollbackAllowance);
		}
		return value;
	}
	generateOrAbortCore(unixTsMs, rollbackAllowance) {
		const MAX_COUNTER = 4398046511103;
		if (!Number.isInteger(unixTsMs) || unixTsMs < 1 || unixTsMs > 0xffffffffffff) throw new RangeError("`unixTsMs` must be a 48-bit positive integer");
		if (rollbackAllowance < 0 || rollbackAllowance > 0xffffffffffff) throw new RangeError("`rollbackAllowance` out of reasonable range");
		if (unixTsMs > this.timestamp) {
			this.timestamp = unixTsMs;
			this.resetCounter();
		} else {
			if (!(unixTsMs + rollbackAllowance >= this.timestamp)) return;
			this.counter++;
			if (this.counter > MAX_COUNTER) {
				this.timestamp++;
				this.resetCounter();
			}
		}
		return UUID.fromFieldsV7(this.timestamp, Math.trunc(this.counter / 2 ** 30), this.counter & 2 ** 30 - 1, this.random.nextUint32());
	}
	resetCounter() {
		this.counter = 1024 * this.random.nextUint32() + (1023 & this.random.nextUint32());
	}
	generateV4() {
		const bytes = new Uint8Array(Uint32Array.of(this.random.nextUint32(), this.random.nextUint32(), this.random.nextUint32(), this.random.nextUint32()).buffer);
		bytes[6] = 64 | bytes[6] >>> 4;
		bytes[8] = 128 | bytes[8] >>> 2;
		return UUID.ofInner(bytes);
	}
};
const getDefaultRandom = () => ({ nextUint32: () => 65536 * Math.trunc(65536 * Math.random()) + Math.trunc(65536 * Math.random()) });
let defaultGenerator;
const uuidv7 = () => uuidv7obj().toString();
const uuidv7obj = () => (defaultGenerator || (defaultGenerator = new V7Generator())).generate();
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/promise-queue.mjs
var PromiseQueue = class {
	add(promise) {
		const promiseUUID = uuidv7();
		const id = ++this.nextId;
		this.promiseByIds[promiseUUID] = {
			id,
			promise
		};
		promise.catch(() => {}).finally(() => {
			delete this.promiseByIds[promiseUUID];
		});
		return promise;
	}
	async join() {
		let promises = Object.values(this.promiseByIds).map((item) => item.promise);
		let length = promises.length;
		while (length > 0) {
			await Promise.all(promises);
			promises = Object.values(this.promiseByIds).map((item) => item.promise);
			length = promises.length;
		}
	}
	getPromises(ignoredPromises = [], maxId = this.nextId) {
		const ignoredPromiseSet = new Set(ignoredPromises);
		return Object.values(this.promiseByIds).filter((item) => item.id <= maxId && !ignoredPromiseSet.has(item.promise)).map((item) => item.promise);
	}
	get maxId() {
		return this.nextId;
	}
	get length() {
		return Object.keys(this.promiseByIds).length;
	}
	constructor() {
		this.promiseByIds = {};
		this.nextId = 0;
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/logger.mjs
function createConsole(consoleLike = console) {
	return {
		log: consoleLike.log.bind(consoleLike),
		warn: consoleLike.warn.bind(consoleLike),
		error: consoleLike.error.bind(consoleLike),
		debug: consoleLike.debug.bind(consoleLike)
	};
}
const _createLogger = (prefix, maybeCall, consoleLike) => {
	function _log(level, ...args) {
		maybeCall(() => {
			const consoleMethod = consoleLike[level];
			consoleMethod(prefix, ...args);
		});
	}
	return {
		debug: (...args) => {
			_log("debug", ...args);
		},
		info: (...args) => {
			_log("log", ...args);
		},
		warn: (...args) => {
			_log("warn", ...args);
		},
		error: (...args) => {
			_log("error", ...args);
		},
		critical: (...args) => {
			consoleLike["error"](prefix, ...args);
		},
		createLogger: (additionalPrefix) => _createLogger(`${prefix} ${additionalPrefix}`, maybeCall, consoleLike)
	};
};
const passThrough = (fn) => fn();
function createLogger(prefix, maybeCall = passThrough) {
	return _createLogger(prefix, maybeCall, createConsole());
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/user-agent-utils.mjs
const MOBILE = "Mobile";
const TABLET = "Tablet";
const NINTENDO = "Nintendo";
const PLAYSTATION = "PlayStation";
const XBOX = "Xbox";
const WINDOWS = "Windows";
"" + MOBILE.toLowerCase();
"" + TABLET.toLowerCase();
new RegExp(XBOX, "i");
new RegExp(NINTENDO, "i"), new RegExp(PLAYSTATION, "i"), new RegExp(WINDOWS, "i");
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/utils/index.mjs
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function isValidUUID(value) {
	return "string" == typeof value && UUID_REGEX.test(value);
}
function getEventUuid(uuid, generateUuid) {
	return isValidUUID(uuid) ? uuid : generateUuid();
}
function removeTrailingSlash(url) {
	return url?.replace(/\/+$/, "");
}
async function retriable(fn, props) {
	let lastError = null;
	for (let i = 0; i < props.retryCount + 1; i++) {
		if (i > 0) await new Promise((r) => setTimeout(r, props.retryDelay));
		try {
			return await fn();
		} catch (e) {
			lastError = e;
			if (!props.retryCheck(e)) throw e;
		}
	}
	throw lastError;
}
function currentISOTime() {
	return (/* @__PURE__ */ new Date()).toISOString();
}
function safeSetTimeout(fn, timeout) {
	const t = setTimeout(fn, timeout);
	t?.unref && t?.unref();
	return t;
}
async function raceWithTimeout(promise, timeoutMs, onTimeout) {
	let timeoutHandle;
	try {
		return await Promise.race([promise, new Promise((resolve, reject) => {
			timeoutHandle = safeSetTimeout(() => {
				try {
					onTimeout?.();
					resolve();
				} catch (error) {
					reject(error);
				}
			}, timeoutMs);
		})]);
	} finally {
		clearTimeout(timeoutHandle);
	}
}
const isError = (x) => x instanceof Error;
function allSettled(promises) {
	return Promise.all(promises.map((p) => (p ?? Promise.resolve()).then((value) => ({
		status: "fulfilled",
		value
	}), (reason) => ({
		status: "rejected",
		reason
	}))));
}
({
	trace: {
		text: "TRACE",
		number: 1
	},
	debug: {
		text: "DEBUG",
		number: 5
	},
	info: {
		text: "INFO",
		number: 9
	},
	warn: {
		text: "WARN",
		number: 13
	},
	error: {
		text: "ERROR",
		number: 17
	},
	fatal: {
		text: "FATAL",
		number: 21
	}
}).info;
function toOtlpAnyValue(value) {
	if (isBoolean(value)) return { boolValue: value };
	if ("number" == typeof value) {
		if (!Number.isFinite(value)) return { stringValue: String(value) };
		if (Number.isInteger(value)) return { intValue: value };
		return { doubleValue: value };
	}
	if ("string" == typeof value) return { stringValue: value };
	if (isArray(value)) return { arrayValue: { values: value.map((v) => toOtlpAnyValue(v)) } };
	try {
		return { stringValue: JSON.stringify(value) };
	} catch {
		return { stringValue: String(value) };
	}
}
function toOtlpKeyValueList(attrs) {
	const result = [];
	for (const key in attrs) {
		const value = attrs[key];
		if (!(isNull(value) || isUndefined(value))) result.push({
			key,
			value: toOtlpAnyValue(value)
		});
	}
	return result;
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/metrics/metrics-utils.mjs
const DEFAULT_HISTOGRAM_BOUNDS = [
	0,
	5,
	10,
	25,
	50,
	75,
	100,
	250,
	500,
	750,
	1e3,
	2500,
	5e3,
	7500,
	1e4
];
function msToUnixNano(ms) {
	return String(ms) + "000000";
}
function seriesKey(type, name, unit, attributes) {
	let attrsKey = "";
	if (attributes) attrsKey = Object.keys(attributes).sort().map((k) => `${JSON.stringify(k)}:${JSON.stringify(attributes[k])}`).join(",");
	return `${type}\u0000${name}\u0000${unit ?? ""}\u0000${attrsKey}`;
}
function bucketIndexFor(value, bounds) {
	for (let i = 0; i < bounds.length; i++) if (value <= bounds[i]) return i;
	return bounds.length;
}
function buildMetricsResourceAttributes(config, scopeName, scopeVersion) {
	return {
		...config.resourceAttributes,
		"service.name": config.serviceName || "unknown_service",
		...config.environment && { "deployment.environment": config.environment },
		...config.serviceVersion && { "service.version": config.serviceVersion },
		"telemetry.sdk.name": scopeName,
		"telemetry.sdk.version": scopeVersion
	};
}
function buildOtlpMetricsPayload(metrics, resourceAttributes, scopeName, scopeVersion) {
	return { resourceMetrics: [{
		resource: { attributes: toOtlpKeyValueList(resourceAttributes) },
		scopeMetrics: [{
			scope: {
				name: scopeName,
				version: scopeVersion
			},
			metrics
		}]
	}] };
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/metrics/config.mjs
const DEFAULT_FLUSH_INTERVAL_MS = 1e4;
const DEFAULT_MAX_SERIES_PER_FLUSH = 1e3;
function resolveMetricsConfig(config) {
	const resourceAttributes = config?.resourceAttributes;
	return {
		serviceName: resourceAttributes?.["service.name"] ?? config?.serviceName,
		serviceVersion: resourceAttributes?.["service.version"] ?? config?.serviceVersion,
		environment: resourceAttributes?.["deployment.environment"] ?? config?.environment,
		resourceAttributes,
		beforeSend: config?.beforeSend,
		flushIntervalMs: config?.flushIntervalMs ?? DEFAULT_FLUSH_INTERVAL_MS,
		maxSeriesPerFlush: config?.maxSeriesPerFlush ?? DEFAULT_MAX_SERIES_PER_FLUSH
	};
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/metrics/index.mjs
const OTLP_TEMPORALITY_DELTA = 1;
var PostHogMetrics = class {
	constructor(_instance, _config, _logger) {
		this._instance = _instance;
		this._config = _config;
		this._logger = _logger;
		this._series = /* @__PURE__ */ new Map();
		this._flushPromise = null;
		this._seriesCapWarned = false;
		this._typeByName = /* @__PURE__ */ new Map();
		this._typeCollisionWarned = /* @__PURE__ */ new Set();
		this._generation = 0;
	}
	count(name, value = 1, options) {
		this._capture({
			name,
			type: "count",
			value,
			unit: options?.unit,
			attributes: options?.attributes
		});
	}
	gauge(name, value, options) {
		this._capture({
			name,
			type: "gauge",
			value,
			unit: options?.unit,
			attributes: options?.attributes
		});
	}
	histogram(name, value, options) {
		this._capture({
			name,
			type: "histogram",
			value,
			unit: options?.unit,
			attributes: options?.attributes
		});
	}
	flush() {
		const prev = this._flushPromise;
		const run = async () => {
			if (prev) await prev.catch(() => {});
			await this._doFlush();
		};
		const p = run().finally(() => {
			if (this._flushPromise === p) this._flushPromise = null;
		});
		this._flushPromise = p;
		return p;
	}
	drainWindow() {
		if (0 === this._series.size) return null;
		const window = this._series;
		this._series = /* @__PURE__ */ new Map();
		this._seriesCapWarned = false;
		this._typeByName = /* @__PURE__ */ new Map();
		this._typeCollisionWarned = /* @__PURE__ */ new Set();
		return this._buildPayload(window);
	}
	reset() {
		this._generation++;
		this._clearFlushTimer();
		this._series = /* @__PURE__ */ new Map();
		this._flushPromise = null;
		this._seriesCapWarned = false;
		this._typeByName = /* @__PURE__ */ new Map();
		this._typeCollisionWarned = /* @__PURE__ */ new Set();
	}
	_capture(sample) {
		if (this._instance.isDisabled || this._instance.optedOut) return;
		const filtered = this._runBeforeSend(sample);
		if (null === filtered) return;
		if (!filtered.name || "string" != typeof filtered.name) return void this._logger.warn("Dropping metric with empty name");
		if ("number" != typeof filtered.value || !Number.isFinite(filtered.value)) return void this._logger.warn(`Dropping metric '${filtered.name}': value must be a finite number`);
		if ("count" === filtered.type && filtered.value < 0) return void this._logger.warn(`Dropping count '${filtered.name}': counters are monotonic, value must be >= 0`);
		let attributes;
		let key;
		try {
			attributes = filtered.attributes ? { ...filtered.attributes } : void 0;
			key = seriesKey(filtered.type, filtered.name, filtered.unit, attributes);
		} catch (e) {
			this._logger.warn(`Dropping metric '${filtered.name}': attributes could not be serialized`, e);
			return;
		}
		let state = this._series.get(key);
		if (!state) {
			if (!this._admitNewSeries()) return;
			state = {
				name: filtered.name,
				type: filtered.type,
				unit: filtered.unit,
				attributes,
				windowStartMs: Date.now()
			};
			this._series.set(key, state);
		}
		const seenType = this._typeByName.get(filtered.name);
		if (void 0 === seenType) this._typeByName.set(filtered.name, filtered.type);
		else if (seenType !== filtered.type && !this._typeCollisionWarned.has(filtered.name)) {
			this._typeCollisionWarned.add(filtered.name);
			this._logger.warn(`Metric name '${filtered.name}' is already used as a ${seenType}; recording it as a ${filtered.type} too will blend both series in charts. Use a distinct name.`);
		}
		this._fold(state, filtered.value);
		this._armFlushTimer();
	}
	_admitNewSeries() {
		if (this._series.size < this._config.maxSeriesPerFlush) return true;
		if (!this._seriesCapWarned) {
			this._seriesCapWarned = true;
			this._logger.warn(`Metric series cap reached (${this._config.maxSeriesPerFlush} per flush window); dropping new series until the next flush. Reduce attribute cardinality.`);
		}
		return false;
	}
	_fold(state, value) {
		switch (state.type) {
			case "count":
				state.total = (state.total ?? 0) + value;
				break;
			case "gauge":
				state.last = value;
				break;
			case "histogram": {
				if (!state.hist) state.hist = {
					count: 0,
					sum: 0,
					min: value,
					max: value,
					bucketCounts: new Array(DEFAULT_HISTOGRAM_BOUNDS.length + 1).fill(0)
				};
				const hist = state.hist;
				hist.count += 1;
				hist.sum += value;
				hist.min = Math.min(hist.min, value);
				hist.max = Math.max(hist.max, value);
				hist.bucketCounts[bucketIndexFor(value, DEFAULT_HISTOGRAM_BOUNDS)] += 1;
				break;
			}
		}
	}
	_runBeforeSend(sample) {
		const beforeSend = this._config.beforeSend;
		if (!beforeSend) return sample;
		const fns = isArray(beforeSend) ? beforeSend : [beforeSend];
		let result = sample;
		for (const fn of fns) try {
			const next = fn(result);
			if (!next) {
				this._logger.info("Metric was rejected in beforeSend function");
				return null;
			}
			result = next;
		} catch (e) {
			this._logger.error("Error in beforeSend function for metric:", e);
			return null;
		}
		return result;
	}
	_armFlushTimer() {
		if (this._flushTimer) return;
		this._flushTimer = safeSetTimeout(() => {
			this._flushTimer = void 0;
			this.flush().catch((e) => {
				this._logger.error("Metrics flush failed:", e);
			});
		}, this._config.flushIntervalMs);
	}
	_clearFlushTimer() {
		if (this._flushTimer) {
			clearTimeout(this._flushTimer);
			this._flushTimer = void 0;
		}
	}
	async _doFlush() {
		if (0 === this._series.size) return;
		const window = this._series;
		this._series = /* @__PURE__ */ new Map();
		this._seriesCapWarned = false;
		this._typeByName = /* @__PURE__ */ new Map();
		this._typeCollisionWarned = /* @__PURE__ */ new Set();
		const generation = this._generation;
		const outcome = await this._instance._sendMetricsBatch(this._buildPayload(window));
		if (generation !== this._generation) return;
		switch (outcome.kind) {
			case "ok": return;
			case "retry-later":
				this._mergeWindowBack(window);
				this._armFlushTimer();
				return;
			case "too-large":
				this._logger.warn("Metrics batch exceeded the server size limit and was dropped");
				return;
			case "fatal":
				this._logger.error("Failed to send metrics batch:", outcome.error);
				return;
		}
	}
	_buildPayload(window) {
		return buildOtlpMetricsPayload(this._buildMetrics(window), buildMetricsResourceAttributes(this._config, this._instance.getLibraryId(), this._instance.getLibraryVersion()), this._instance.getLibraryId(), this._instance.getLibraryVersion());
	}
	_buildMetrics(window) {
		const nowNano = msToUnixNano(Date.now());
		const byMetric = /* @__PURE__ */ new Map();
		for (const state of window.values()) {
			const metricKey = seriesKey(state.type, state.name, state.unit, void 0);
			let metric = byMetric.get(metricKey);
			if (!metric) {
				metric = {
					name: state.name,
					...state.unit && { unit: state.unit }
				};
				if ("count" === state.type) metric.sum = {
					aggregationTemporality: OTLP_TEMPORALITY_DELTA,
					isMonotonic: true,
					dataPoints: []
				};
				else if ("gauge" === state.type) metric.gauge = { dataPoints: [] };
				else metric.histogram = {
					aggregationTemporality: OTLP_TEMPORALITY_DELTA,
					dataPoints: []
				};
				byMetric.set(metricKey, metric);
			}
			const attributes = toOtlpKeyValueList(state.attributes ?? {});
			const startNano = msToUnixNano(state.windowStartMs);
			if ("count" === state.type) {
				const dp = {
					attributes,
					startTimeUnixNano: startNano,
					timeUnixNano: nowNano,
					asDouble: state.total ?? 0
				};
				metric.sum.dataPoints.push(dp);
			} else if ("gauge" === state.type) {
				const dp = {
					attributes,
					timeUnixNano: nowNano,
					asDouble: state.last ?? 0
				};
				metric.gauge.dataPoints.push(dp);
			} else if (state.hist) {
				const dp = {
					attributes,
					startTimeUnixNano: startNano,
					timeUnixNano: nowNano,
					count: state.hist.count,
					sum: state.hist.sum,
					min: state.hist.min,
					max: state.hist.max,
					bucketCounts: state.hist.bucketCounts,
					explicitBounds: DEFAULT_HISTOGRAM_BOUNDS
				};
				metric.histogram.dataPoints.push(dp);
			}
		}
		return Array.from(byMetric.values());
	}
	_mergeWindowBack(window) {
		for (const [key, old] of window) {
			const current = this._series.get(key);
			if (!current) {
				if (this._admitNewSeries()) this._series.set(key, old);
				continue;
			}
			current.windowStartMs = Math.min(current.windowStartMs, old.windowStartMs);
			switch (current.type) {
				case "count":
					current.total = (current.total ?? 0) + (old.total ?? 0);
					break;
				case "gauge": break;
				case "histogram": if (old.hist) if (current.hist) {
					current.hist.count += old.hist.count;
					current.hist.sum += old.hist.sum;
					current.hist.min = Math.min(current.hist.min, old.hist.min);
					current.hist.max = Math.max(current.hist.max, old.hist.max);
					for (let i = 0; i < current.hist.bucketCounts.length; i++) current.hist.bucketCounts[i] += old.hist.bucketCounts[i];
				} else current.hist = old.hist;
			}
		}
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/eventemitter.mjs
var SimpleEventEmitter = class {
	constructor() {
		this.events = {};
		this.events = {};
	}
	on(event, listener) {
		if (!this.events[event]) this.events[event] = [];
		this.events[event].push(listener);
		return () => {
			this.events[event] = this.events[event].filter((x) => x !== listener);
		};
	}
	emit(event, payload) {
		for (const listener of this.events[event] || []) listener(payload);
		for (const listener of this.events["*"] || []) listener(event, payload);
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/chunk-ids.mjs
let parsedStackResults;
let lastKeysCount;
let cachedFilenameChunkIds;
function getFilenameToChunkIdMap(stackParser) {
	const chunkIdMap = globalThis._posthogChunkIds;
	if (!chunkIdMap) return;
	const chunkIdKeys = Object.keys(chunkIdMap);
	if (cachedFilenameChunkIds && chunkIdKeys.length === lastKeysCount) return cachedFilenameChunkIds;
	lastKeysCount = chunkIdKeys.length;
	cachedFilenameChunkIds = chunkIdKeys.reduce((acc, stackKey) => {
		if (!parsedStackResults) parsedStackResults = {};
		const result = parsedStackResults[stackKey];
		if (result) acc[result[0]] = result[1];
		else {
			const parsedStack = stackParser(stackKey);
			for (let i = parsedStack.length - 1; i >= 0; i--) {
				const filename = parsedStack[i]?.filename;
				const chunkId = chunkIdMap[stackKey];
				if (filename && chunkId) {
					acc[filename] = chunkId;
					parsedStackResults[stackKey] = [filename, chunkId];
					break;
				}
			}
		}
		return acc;
	}, {});
	return cachedFilenameChunkIds;
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/error-properties-builder.mjs
const MAX_CAUSE_RECURSION = 4;
var ErrorPropertiesBuilder = class {
	constructor(coercers, stackParser, modifiers = []) {
		this.coercers = coercers;
		this.stackParser = stackParser;
		this.modifiers = modifiers;
	}
	buildFromUnknown(input, hint = {}) {
		const mechanism = hint && hint.mechanism || {
			handled: true,
			type: "generic"
		};
		const exceptionWithCause = this.buildCoercingContext(mechanism, hint, 0).apply(input);
		const parsingContext = this.buildParsingContext(hint);
		const exceptionWithStack = this.parseStacktrace(exceptionWithCause, parsingContext);
		return {
			$exception_list: this.convertToExceptionList(exceptionWithStack, mechanism),
			$exception_level: "error"
		};
	}
	async modifyFrames(exceptionList) {
		for (const exc of exceptionList) if (exc.stacktrace && exc.stacktrace.frames && isArray(exc.stacktrace.frames)) exc.stacktrace.frames = await this.applyModifiers(exc.stacktrace.frames);
		return exceptionList;
	}
	coerceFallback(ctx) {
		return {
			type: "Error",
			value: "Unknown error",
			stack: ctx.syntheticException?.stack,
			synthetic: true
		};
	}
	parseStacktrace(err, ctx) {
		let cause;
		if (null != err.cause) cause = this.parseStacktrace(err.cause, ctx);
		let stack;
		if ("" != err.stack && null != err.stack) stack = this.applyChunkIds(this.stackParser(err.stack, err.synthetic ? ctx.skipFirstLines : 0), ctx.chunkIdMap);
		return {
			...err,
			cause,
			stack
		};
	}
	applyChunkIds(frames, chunkIdMap) {
		return frames.map((frame) => {
			if (frame.filename && chunkIdMap) frame.chunk_id = chunkIdMap[frame.filename];
			return frame;
		});
	}
	applyCoercers(input, ctx) {
		for (const adapter of this.coercers) if (adapter.match(input)) return adapter.coerce(input, ctx);
		return this.coerceFallback(ctx);
	}
	async applyModifiers(frames) {
		let newFrames = frames;
		for (const modifier of this.modifiers) newFrames = await modifier(newFrames);
		return newFrames;
	}
	convertToExceptionList(exceptionWithStack, mechanism) {
		const currentException = {
			type: exceptionWithStack.type,
			value: exceptionWithStack.value,
			mechanism: {
				type: mechanism.type ?? "generic",
				handled: mechanism.handled ?? true,
				synthetic: exceptionWithStack.synthetic ?? false
			}
		};
		if (exceptionWithStack.stack) currentException.stacktrace = {
			type: "raw",
			frames: exceptionWithStack.stack
		};
		const exceptionList = [currentException];
		if (null != exceptionWithStack.cause) exceptionList.push(...this.convertToExceptionList(exceptionWithStack.cause, {
			...mechanism,
			handled: true
		}));
		return exceptionList;
	}
	buildParsingContext(hint) {
		return {
			chunkIdMap: getFilenameToChunkIdMap(this.stackParser),
			skipFirstLines: hint.skipFirstLines ?? 1
		};
	}
	buildCoercingContext(mechanism, hint, depth = 0) {
		const coerce = (input, depth) => {
			if (!(depth <= MAX_CAUSE_RECURSION)) return;
			{
				const ctx = this.buildCoercingContext(mechanism, hint, depth);
				return this.applyCoercers(input, ctx);
			}
		};
		return {
			...hint,
			syntheticException: 0 == depth ? hint.syntheticException : void 0,
			mechanism,
			apply: (input) => coerce(input, depth),
			next: (input) => coerce(input, depth + 1)
		};
	}
};
function createFrame(platform, filename, func, lineno, colno) {
	const frame = {
		platform,
		filename,
		function: "<anonymous>" === func ? "?" : func,
		in_app: true
	};
	if (!isUndefined(lineno)) frame.lineno = lineno;
	if (!isUndefined(colno)) frame.colno = colno;
	return frame;
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/parsers/safari.mjs
const extractSafariExtensionDetails = (func, filename) => {
	const isSafariExtension = -1 !== func.indexOf("safari-extension");
	const isSafariWebExtension = -1 !== func.indexOf("safari-web-extension");
	return isSafariExtension || isSafariWebExtension ? [-1 !== func.indexOf("@") ? func.split("@")[0] : "?", isSafariExtension ? `safari-extension:${filename}` : `safari-web-extension:${filename}`] : [func, filename];
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/parsers/chrome.mjs
const chromeRegexNoFnName = /^\s*at (\S+?)(?::(\d+))(?::(\d+))\s*$/i;
const chromeRegex = /^\s*at (?:(.+?\)(?: \[.+\])?|.*?) ?\((?:address at )?)?(?:async )?((?:<anonymous>|[-a-z]+:|.*bundle|\/)?.*?)(?::(\d+))?(?::(\d+))?\)?\s*$/i;
const chromeEvalRegex = /\((\S*)(?::(\d+))(?::(\d+))\)/;
const chromeStackLineParser = (line, platform) => {
	const noFnParts = chromeRegexNoFnName.exec(line);
	if (noFnParts) {
		const [, filename, line, col] = noFnParts;
		return createFrame(platform, filename, "?", +line, +col);
	}
	const parts = chromeRegex.exec(line);
	if (parts) {
		if (parts[2] && 0 === parts[2].indexOf("eval")) {
			const subMatch = chromeEvalRegex.exec(parts[2]);
			if (subMatch) {
				parts[2] = subMatch[1];
				parts[3] = subMatch[2];
				parts[4] = subMatch[3];
			}
		}
		const [func, filename] = extractSafariExtensionDetails(parts[1] || "?", parts[2]);
		return createFrame(platform, filename, func, parts[3] ? +parts[3] : void 0, parts[4] ? +parts[4] : void 0);
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/parsers/gecko.mjs
const geckoREgex = /^\s*(.*?)(?:\((.*?)\))?(?:^|@)?((?:[-a-z]+)?:\/.*?|\[native code\]|[^@]*(?:bundle|\d+\.js)|\/[\w\-. /=]+)(?::(\d+))?(?::(\d+))?\s*$/i;
const geckoEvalRegex = /(\S+) line (\d+)(?: > eval line \d+)* > eval/i;
const geckoStackLineParser = (line, platform) => {
	const parts = geckoREgex.exec(line);
	if (parts) {
		if (parts[3] && parts[3].indexOf(" > eval") > -1) {
			const subMatch = geckoEvalRegex.exec(parts[3]);
			if (subMatch) {
				parts[1] = parts[1] || "eval";
				parts[3] = subMatch[1];
				parts[4] = subMatch[2];
				parts[5] = "";
			}
		}
		let filename = parts[3];
		let func = parts[1] || "?";
		[func, filename] = extractSafariExtensionDetails(func, filename);
		return createFrame(platform, filename, func, parts[4] ? +parts[4] : void 0, parts[5] ? +parts[5] : void 0);
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/parsers/node.mjs
const FILENAME_MATCH = /^\s*[-]{4,}$/;
const FULL_MATCH = /at (?:async )?(?:(.+?)\s+\()?(?:(.+):(\d+):(\d+)?|([^)]+))\)?/;
const PROMISE_COMBINATOR = /^Promise\.(?:all|any)$/;
const PROMISE_INDEX = /^index \d+$/;
const PROMISE_FRAME_FILENAME = "node:internal/promise";
const nodeStackLineParser = (line, platform) => {
	const lineMatch = line.match(FULL_MATCH);
	if (lineMatch) {
		let object;
		let method;
		let functionName;
		let typeName;
		let methodName;
		if (lineMatch[1]) {
			functionName = lineMatch[1];
			let methodStart = functionName.lastIndexOf(".");
			if ("." === functionName[methodStart - 1]) methodStart--;
			if (methodStart > 0) {
				object = functionName.slice(0, methodStart);
				method = functionName.slice(methodStart + 1);
				const objectEnd = object.indexOf(".Module");
				if (objectEnd > 0) {
					functionName = functionName.slice(objectEnd + 1);
					object = object.slice(0, objectEnd);
				}
			}
			typeName = void 0;
		}
		if (method) {
			typeName = object;
			methodName = method;
		}
		if ("<anonymous>" === method) {
			methodName = void 0;
			functionName = void 0;
		}
		if (void 0 === functionName) {
			methodName = methodName || "?";
			functionName = typeName ? `${typeName}.${methodName}` : methodName;
		}
		let filename = lineMatch[2]?.startsWith("file://") ? lineMatch[2].slice(7) : lineMatch[2];
		const isNative = "native" === lineMatch[5];
		if (filename?.match(/\/[A-Z]:/)) filename = filename.slice(1);
		if (!filename && lineMatch[5] && !isNative) filename = lineMatch[5];
		if (PROMISE_COMBINATOR.test(functionName) && PROMISE_INDEX.test(filename || "")) filename = PROMISE_FRAME_FILENAME;
		return {
			filename: filename ? decodeURI(filename) : void 0,
			module: void 0,
			function: functionName,
			lineno: _parseIntOrUndefined(lineMatch[3]),
			colno: _parseIntOrUndefined(lineMatch[4]),
			in_app: filenameIsInApp(filename || "", isNative),
			platform
		};
	}
	if (line.match(FILENAME_MATCH)) return {
		filename: line,
		platform
	};
};
function filenameIsInApp(filename, isNative = false) {
	return !(isNative || filename && !filename.startsWith("/") && !filename.match(/^[A-Z]:/) && !filename.startsWith(".") && !filename.match(/^[a-zA-Z]([a-zA-Z0-9.\-+])*:\/\//)) && void 0 !== filename && !filename.includes("node_modules/");
}
function _parseIntOrUndefined(input) {
	return parseInt(input || "", 10) || void 0;
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/parsers/index.mjs
const WEBPACK_ERROR_REGEXP = /\(error: (.*)\)/;
const STACKTRACE_FRAME_LIMIT = 50;
function reverseAndStripFrames(stack) {
	if (!stack.length) return [];
	const localStack = Array.from(stack);
	localStack.reverse();
	return localStack.slice(0, STACKTRACE_FRAME_LIMIT).map((frame) => ({
		...frame,
		filename: frame.filename || getLastStackFrame(localStack).filename,
		function: frame.function || "?"
	}));
}
function getLastStackFrame(arr) {
	return arr[arr.length - 1] || {};
}
function createDefaultStackParser() {
	return createStackParser("web:javascript", chromeStackLineParser, geckoStackLineParser);
}
function createStackParser(platform, ...parsers) {
	return (stack, skipFirstLines = 0) => {
		const frames = [];
		const lines = stack.split("\n");
		for (let i = skipFirstLines; i < lines.length; i++) {
			const line = lines[i];
			if (line.length > 1024) continue;
			const cleanedLine = WEBPACK_ERROR_REGEXP.test(line) ? line.replace(WEBPACK_ERROR_REGEXP, "$1") : line;
			if (!cleanedLine.match(/\S*Error: /)) {
				for (const parser of parsers) {
					const frame = parser(cleanedLine, platform);
					if (frame) {
						frames.push(frame);
						break;
					}
				}
				if (frames.length >= STACKTRACE_FRAME_LIMIT) break;
			}
		}
		return reverseAndStripFrames(frames);
	};
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/coercers/error-coercer.mjs
var ErrorCoercer = class {
	match(err) {
		return isError$1(err);
	}
	coerce(err, ctx) {
		return {
			type: this.getType(err),
			value: this.getMessage(err, ctx),
			stack: this.getStack(err),
			cause: err.cause ? ctx.next(err.cause) : void 0,
			synthetic: false
		};
	}
	getType(err) {
		return err.name || err.constructor.name;
	}
	getMessage(err, _ctx) {
		const message = err.message;
		if (message.error && "string" == typeof message.error.message) return String(message.error.message);
		return String(message);
	}
	getStack(err) {
		return err.stacktrace || err.stack || void 0;
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/coercers/string-coercer.mjs
const ERROR_TYPES_PATTERN = /^(?:[Uu]ncaught (?:exception: )?)?(?:((?:Eval|Internal|Range|Reference|Syntax|Type|URI|)Error): )?(.*)$/i;
var StringCoercer = class {
	match(input) {
		return "string" == typeof input;
	}
	coerce(input, ctx) {
		const [type, value] = this.getInfos(input);
		return {
			type: type ?? "Error",
			value: value ?? input,
			stack: ctx.syntheticException?.stack,
			synthetic: true
		};
	}
	getInfos(candidate) {
		let type = "Error";
		let value = candidate;
		const groups = candidate.match(ERROR_TYPES_PATTERN);
		if (groups) {
			type = groups[1];
			value = groups[2];
		}
		return [type, value];
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/types.mjs
const severityLevels = [
	"fatal",
	"error",
	"warning",
	"log",
	"info",
	"debug"
];
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/coercers/utils.mjs
function extractExceptionKeysForMessage(err, maxLength = 40) {
	const keys = Object.keys(err);
	keys.sort();
	if (!keys.length) return "[object has no keys]";
	for (let i = keys.length; i > 0; i--) {
		const serialized = keys.slice(0, i).join(", ");
		if (!(serialized.length > maxLength)) {
			if (i === keys.length) return serialized;
			return serialized.length <= maxLength ? serialized : `${serialized.slice(0, maxLength)}...`;
		}
	}
	return "";
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/coercers/object-coercer.mjs
var ObjectCoercer = class {
	match(candidate) {
		return "object" == typeof candidate && null !== candidate;
	}
	coerce(candidate, ctx) {
		const errorProperty = this.getErrorPropertyFromObject(candidate);
		if (errorProperty) return ctx.apply(errorProperty);
		return {
			type: this.getType(candidate),
			value: this.getValue(candidate),
			stack: this.getStack(candidate) ?? ctx.syntheticException?.stack,
			level: this.isSeverityLevel(candidate.level) ? candidate.level : "error",
			synthetic: true
		};
	}
	getType(err) {
		return isEvent(err) ? err.constructor.name : "Error";
	}
	getValue(err) {
		if ("name" in err && "string" == typeof err.name) {
			let message = `'${err.name}' captured as exception`;
			if ("message" in err && "string" == typeof err.message) message += ` with message: '${err.message}'`;
			return message;
		}
		if ("message" in err && "string" == typeof err.message) return err.message;
		const className = this.getObjectClassName(err);
		const keys = extractExceptionKeysForMessage(err);
		return `${className && "Object" !== className ? `'${className}'` : "Object"} captured as exception with keys: ${keys}`;
	}
	isSeverityLevel(x) {
		return isString(x) && !isEmptyString(x) && severityLevels.indexOf(x) >= 0;
	}
	getStack(candidate) {
		try {
			if (isString(candidate.stacktrace) && candidate.stacktrace.length > 0) return candidate.stacktrace;
			return isString(candidate.stack) && candidate.stack.length > 0 ? candidate.stack : void 0;
		} catch {
			return;
		}
	}
	getErrorPropertyFromObject(obj) {
		for (const prop in obj) if (Object.prototype.hasOwnProperty.call(obj, prop)) {
			const value = obj[prop];
			if (isError(value)) return value;
		}
	}
	getObjectClassName(obj) {
		try {
			const prototype = Object.getPrototypeOf(obj);
			return prototype ? prototype.constructor.name : void 0;
		} catch (e) {
			return;
		}
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/coercers/event-coercer.mjs
var EventCoercer = class {
	match(err) {
		return isEvent(err);
	}
	coerce(evt, ctx) {
		const constructorName = evt.constructor.name;
		return {
			type: constructorName,
			value: `${constructorName} captured as exception with keys: ${extractExceptionKeysForMessage(evt)}`,
			stack: ctx.syntheticException?.stack,
			synthetic: true
		};
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/coercers/primitive-coercer.mjs
var PrimitiveCoercer = class {
	match(candidate) {
		return isPrimitive(candidate);
	}
	coerce(value, ctx) {
		return {
			type: "Error",
			value: `Primitive value captured as exception: ${String(value)}`,
			stack: ctx.syntheticException?.stack,
			synthetic: true
		};
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/utils.mjs
var ReduceableCache = class {
	constructor(_maxSize) {
		this._maxSize = _maxSize;
		this._cache = /* @__PURE__ */ new Map();
	}
	get(key) {
		const value = this._cache.get(key);
		if (void 0 === value) return;
		this._cache.delete(key);
		this._cache.set(key, value);
		return value;
	}
	set(key, value) {
		this._cache.set(key, value);
	}
	reduce() {
		while (this._cache.size >= this._maxSize) {
			const value = this._cache.keys().next().value;
			if (value) this._cache.delete(value);
		}
	}
};
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/exception-steps.mjs
const EXCEPTION_STEP_INTERNAL_FIELDS = {
	MESSAGE: "$message",
	TIMESTAMP: "$timestamp"
};
EXCEPTION_STEP_INTERNAL_FIELDS.MESSAGE, EXCEPTION_STEP_INTERNAL_FIELDS.TIMESTAMP;
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/error-tracking/release.mjs
function getInjectedReleaseId() {
	const injected = globalThis._posthogReleaseId;
	return "string" == typeof injected && injected.length > 0 ? injected : void 0;
}
//#endregion
//#region ../../node_modules/.bun/@posthog+core@1.46.8/node_modules/@posthog/core/dist/posthog-core-stateless.mjs
var PostHogFetchHttpError = class extends Error {
	constructor(response, reqByteLength, responseBodyDeadline, abortController) {
		super("HTTP error while fetching PostHog: status=" + response.status + ", reqByteLength=" + reqByteLength), this.response = response, this.reqByteLength = reqByteLength, this.responseBodyDeadline = responseBodyDeadline, this.abortController = abortController, this.name = "PostHogFetchHttpError", this._bodyReadTimedOut = false;
	}
	get status() {
		return this.response.status;
	}
	get bodyReadTimedOut() {
		return this._bodyReadTimedOut;
	}
	get text() {
		if (!this.responseBodyTextPromise) if (Date.now() >= this.responseBodyDeadline) {
			this._bodyReadTimedOut = true;
			const timeoutError = /* @__PURE__ */ new Error("Response body read timed out");
			timeoutError.name = "AbortError";
			this.cancelResponseBody(timeoutError);
			this.responseBodyTextPromise = Promise.reject(timeoutError);
		} else {
			const responseBodyTimeout = new Promise((_resolve, reject) => {
				this.responseBodyTimer = safeSetTimeout(() => {
					this._bodyReadTimedOut = true;
					const timeoutError = /* @__PURE__ */ new Error("Response body read timed out");
					timeoutError.name = "AbortError";
					reject(timeoutError);
					this.cancelResponseBody(timeoutError);
				}, this.responseBodyDeadline - Date.now());
			});
			let responseBodyText;
			try {
				responseBodyText = Promise.resolve(this.response.text());
			} catch (error) {
				responseBodyText = Promise.reject(error);
			}
			this.responseBodyTextPromise = Promise.race([responseBodyText, responseBodyTimeout]).finally(() => clearTimeout(this.responseBodyTimer));
		}
		return this.responseBodyTextPromise;
	}
	get json() {
		return this.text.then((text) => JSON.parse(text));
	}
	cancelResponseBody(reason) {
		clearTimeout(this.responseBodyTimer);
		if (!this.abortController.signal.aborted) this.abortController.abort(reason);
		(async () => {
			try {
				await this.response.body?.cancel();
			} catch {}
		})();
	}
};
var PostHogFetchNetworkError = class extends Error {
	constructor(error) {
		super("Network error while fetching PostHog", error instanceof Error ? { cause: error } : {}), this.error = error, this.name = "PostHogFetchNetworkError";
	}
};
const applyCallerFeatureFlagOverrides = (target, callerProperties) => {
	for (const key of Object.keys(callerProperties)) if (key.startsWith("$feature/") || "$active_feature_flags" === key) target[key] = callerProperties[key];
};
async function logFlushError(err) {
	if (err instanceof PostHogFetchHttpError) {
		let text = "";
		try {
			text = await err.text;
		} catch {
			if (err.bodyReadTimedOut) text = "<response body read timed out>";
		}
		console.error(`Error while flushing PostHog: message=${err.message}, response body=${text}`, err);
	} else console.error("Error while flushing PostHog", err);
	return Promise.resolve();
}
function isPostHogFetchError(err) {
	return "object" == typeof err && (err instanceof PostHogFetchHttpError || isPostHogFetchNetworkError(err));
}
function isPostHogFetchNetworkError(err) {
	return err instanceof PostHogFetchNetworkError;
}
function isRetryableFlagsFetchError(err) {
	if (err instanceof PostHogFetchHttpError) return 502 === err.status || 504 === err.status;
	if (!(err instanceof PostHogFetchNetworkError)) return false;
	const cause = err.error;
	return "ECONNREFUSED" !== (cause?.code ?? cause?.cause?.code);
}
function isPostHogFetchContentTooLargeError(err) {
	return "object" == typeof err && err instanceof PostHogFetchHttpError && 413 === err.status;
}
function isPostHogFetchRetryableError(err) {
	if (err instanceof PostHogFetchHttpError) return 408 === err.status || 429 === err.status || err.status >= 500;
	return isPostHogFetchNetworkError(err);
}
function isPostHogEventProperties(value) {
	return null !== value && "object" == typeof value && !Array.isArray(value);
}
const DEFAULT_QUEUE_ROUTE = "default";
var PostHogCoreStateless = class {
	getErrorPropertiesBuilder() {
		if (!this._errorPropertiesBuilder) this._errorPropertiesBuilder = this.createErrorPropertiesBuilder();
		return this._errorPropertiesBuilder;
	}
	createErrorPropertiesBuilder() {
		return new ErrorPropertiesBuilder([
			new ErrorCoercer(),
			new ObjectCoercer(),
			new StringCoercer(),
			new PrimitiveCoercer()
		], createDefaultStackParser());
	}
	constructor(apiKey, options = {}) {
		this.flushPromise = null;
		this.pendingFlushPromise = null;
		this.flushPromises = /* @__PURE__ */ new Set();
		this._dequeuedMessagesCount = 0;
		this.shutdownPromise = null;
		this.promiseQueue = new PromiseQueue();
		this._events = new SimpleEventEmitter();
		this._isInitialized = false;
		const normalizedApiKey = "string" == typeof apiKey ? apiKey.trim() : "";
		const normalizedHost = "string" == typeof options.host ? options.host.trim() : "";
		const missingApiKey = !normalizedApiKey;
		this._logger = createLogger("[PostHog]", this.logMsgIfDebug.bind(this));
		if (missingApiKey) this._logger.error("You must pass your PostHog project's api key. The client will be disabled.");
		this.apiKey = normalizedApiKey;
		this.host = removeTrailingSlash(normalizedHost || "https://us.i.posthog.com");
		this.flushAt = options.flushAt ? Math.max(options.flushAt, 1) : 20;
		this.maxBatchSize = Math.max(this.flushAt, options.maxBatchSize ?? 100);
		this.maxQueueSize = Math.max(this.flushAt, options.maxQueueSize ?? 1e3);
		this.flushInterval = options.flushInterval ?? 1e4;
		this.preloadFeatureFlags = options.preloadFeatureFlags ?? true;
		this.defaultOptIn = options.defaultOptIn ?? true;
		this.disableSurveys = options.disableSurveys ?? false;
		this._retryOptions = {
			retryCount: options.fetchRetryCount ?? 3,
			retryDelay: options.fetchRetryDelay ?? 3e3,
			retryCheck: isPostHogFetchRetryableError
		};
		this.requestTimeout = options.requestTimeout ?? 1e4;
		this.featureFlagsRequestTimeoutMs = options.featureFlagsRequestTimeoutMs ?? 3e3;
		this.featureFlagsRequestMaxRetries = options.featureFlagsRequestMaxRetries ?? 1;
		this.remoteConfigRequestTimeoutMs = options.remoteConfigRequestTimeoutMs ?? 3e3;
		this.disableGeoip = options.disableGeoip ?? true;
		this.disabled = (options.disabled ?? false) || missingApiKey;
		this.historicalMigration = options?.historicalMigration ?? false;
		this._initPromise = Promise.resolve();
		this._isInitialized = true;
		this.evaluationContexts = options?.evaluationContexts ?? options?.evaluationEnvironments;
		if (options?.evaluationEnvironments && !options?.evaluationContexts) this._logger.warn("evaluationEnvironments is deprecated. Use evaluationContexts instead. This property will be removed in a future version.");
		this.disableCompression = !isGzipSupported() || (options?.disableCompression ?? false);
	}
	logMsgIfDebug(fn) {
		if (this.isDebug) fn();
	}
	wrap(fn) {
		if (this.disabled) return void this._logger.warn("The client is disabled");
		if (this._isInitialized) return fn();
		this._initPromise.then(() => fn());
	}
	getCommonEventProperties() {
		return {
			$lib: this.getLibraryId(),
			$lib_version: this.getLibraryVersion()
		};
	}
	get optedOut() {
		return this.getPersistedProperty(types_PostHogPersistedProperty.OptedOut) ?? !this.defaultOptIn;
	}
	async optIn() {
		this.wrap(() => {
			this.setPersistedProperty(types_PostHogPersistedProperty.OptedOut, false);
		});
	}
	async optOut() {
		this.wrap(() => {
			this.setPersistedProperty(types_PostHogPersistedProperty.OptedOut, true);
		});
	}
	on(event, cb) {
		return this._events.on(event, cb);
	}
	debug(enabled = true) {
		this.removeDebugCallback?.();
		if (enabled) {
			const removeDebugCallback = this.on("*", (event, payload) => this._logger.info(event, payload));
			this.removeDebugCallback = () => {
				removeDebugCallback();
				this.removeDebugCallback = void 0;
			};
		}
	}
	get isDebug() {
		return !!this.removeDebugCallback;
	}
	get isDisabled() {
		return this.disabled;
	}
	buildPayload(payload) {
		const userProperties = payload.properties || {};
		let properties = {
			...userProperties,
			...this.getCommonEventProperties()
		};
		applyCallerFeatureFlagOverrides(properties, userProperties);
		if ("$feature_flag_called" === payload.event && false === properties.$feature_flag_has_experiment && this.isMinimalFlagCalledEventsEnabled()) properties = minimizeFlagCalledEventProperties(properties);
		return {
			distinct_id: payload.distinct_id,
			event: payload.event,
			properties
		};
	}
	isMinimalFlagCalledEventsEnabled() {
		return false;
	}
	addPendingPromise(promise) {
		return this.promiseQueue.add(promise);
	}
	identifyStateless(distinctId, properties, options) {
		this.wrap(() => {
			const payload = { ...this.buildPayload({
				distinct_id: distinctId,
				event: "$identify",
				properties
			}) };
			this.enqueue("identify", payload, options);
		});
	}
	async identifyStatelessImmediate(distinctId, properties, options) {
		const payload = { ...this.buildPayload({
			distinct_id: distinctId,
			event: "$identify",
			properties
		}) };
		await this.sendImmediate("identify", payload, options);
	}
	captureStateless(distinctId, event, properties, options) {
		this.wrap(() => {
			const payload = this.buildPayload({
				distinct_id: distinctId,
				event,
				properties
			});
			this.enqueue("capture", payload, options);
		});
	}
	async captureStatelessImmediate(distinctId, event, properties, options) {
		const payload = this.buildPayload({
			distinct_id: distinctId,
			event,
			properties
		});
		await this.sendImmediate("capture", payload, options);
	}
	aliasStateless(alias, distinctId, properties, options) {
		this.wrap(() => {
			const payload = this.buildPayload({
				event: "$create_alias",
				distinct_id: distinctId,
				properties: {
					...properties || {},
					distinct_id: distinctId,
					alias
				}
			});
			this.enqueue("alias", payload, options);
		});
	}
	async aliasStatelessImmediate(alias, distinctId, properties, options) {
		const payload = this.buildPayload({
			event: "$create_alias",
			distinct_id: distinctId,
			properties: {
				...properties || {},
				distinct_id: distinctId,
				alias
			}
		});
		await this.sendImmediate("alias", payload, options);
	}
	groupIdentifyStateless(groupType, groupKey, groupProperties, options, distinctId, eventProperties) {
		this.wrap(() => {
			const payload = this.buildPayload({
				distinct_id: distinctId || `$${groupType}_${groupKey}`,
				event: "$groupidentify",
				properties: {
					$group_type: groupType,
					$group_key: groupKey,
					$group_set: groupProperties || {},
					...eventProperties || {}
				}
			});
			this.enqueue("capture", payload, options);
		});
	}
	async groupIdentifyStatelessImmediate(groupType, groupKey, groupProperties, options, distinctId, eventProperties) {
		const payload = this.buildPayload({
			distinct_id: distinctId || `$${groupType}_${groupKey}`,
			event: "$groupidentify",
			properties: {
				$group_type: groupType,
				$group_key: groupKey,
				$group_set: groupProperties || {},
				...eventProperties || {}
			}
		});
		await this.sendImmediate("capture", payload, options);
	}
	async getRemoteConfig() {
		await this._initPromise;
		let host = this.host;
		if ("https://us.i.posthog.com" === host) host = "https://us-assets.i.posthog.com";
		else if ("https://eu.i.posthog.com" === host) host = "https://eu-assets.i.posthog.com";
		const url = `${host}/array/${this.apiKey}/config`;
		const fetchOptions = {
			method: "GET",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json"
			}
		};
		return this.fetchWithRetry(url, fetchOptions, {
			type: "required",
			consume: (response) => response.json()
		}, { retryCount: 0 }, this.remoteConfigRequestTimeoutMs).catch((error) => {
			this._logger.error("Remote config could not be loaded", error);
			this._events.emit("error", error);
		});
	}
	async getFlags(distinctId, groups = {}, personProperties = {}, groupProperties = {}, extraPayload = {}, fetchConfig = false) {
		await this._initPromise;
		const configParam = fetchConfig ? "&config=true" : "";
		const url = `${this.host}/flags/?v=2${configParam}`;
		const requestData = {
			token: this.apiKey,
			distinct_id: distinctId,
			groups,
			person_properties: personProperties,
			group_properties: groupProperties,
			...extraPayload
		};
		if (personProperties.$device_id) requestData.$device_id = personProperties.$device_id;
		if (this.evaluationContexts && this.evaluationContexts.length > 0) requestData.evaluation_contexts = this.evaluationContexts;
		const fetchOptions = {
			method: "POST",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json"
			},
			body: JSON.stringify(requestData)
		};
		this._logger.info("Flags URL", url);
		return this.fetchWithRetry(url, fetchOptions, {
			type: "required",
			consume: (response) => response.json()
		}, {
			retryCount: this.featureFlagsRequestMaxRetries,
			retryCheck: isRetryableFlagsFetchError
		}, this.featureFlagsRequestTimeoutMs).then((response) => ({
			success: true,
			response: normalizeFlagsResponse(response)
		})).catch((error) => {
			this._events.emit("error", error);
			return {
				success: false,
				error: this.categorizeRequestError(error)
			};
		});
	}
	categorizeRequestError(error) {
		if (error instanceof PostHogFetchHttpError) return {
			type: "api_error",
			statusCode: error.status
		};
		if (error instanceof PostHogFetchNetworkError) {
			const cause = error.error;
			if (cause instanceof Error && ("AbortError" === cause.name || "TimeoutError" === cause.name)) return { type: "timeout" };
			return { type: "connection_error" };
		}
		return { type: "unknown_error" };
	}
	async getFeatureFlagStateless(key, distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip) {
		await this._initPromise;
		const flagDetailResponse = await this.getFeatureFlagDetailStateless(key, distinctId, groups, personProperties, groupProperties, disableGeoip);
		if (void 0 === flagDetailResponse) return {
			response: void 0,
			requestId: void 0
		};
		let response = getFeatureFlagValue(flagDetailResponse.response);
		if (void 0 === response) response = false;
		return {
			response,
			requestId: flagDetailResponse.requestId
		};
	}
	async getFeatureFlagDetailStateless(key, distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip) {
		await this._initPromise;
		const flagsResponse = await this.getFeatureFlagDetailsStateless(distinctId, groups, personProperties, groupProperties, disableGeoip, [key]);
		if (void 0 === flagsResponse) return;
		return {
			response: flagsResponse.flags[key],
			requestId: flagsResponse.requestId,
			evaluatedAt: flagsResponse.evaluatedAt
		};
	}
	async getFeatureFlagPayloadStateless(key, distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip) {
		await this._initPromise;
		const payloads = await this.getFeatureFlagPayloadsStateless(distinctId, groups, personProperties, groupProperties, disableGeoip, [key]);
		if (!payloads) return;
		const response = payloads[key];
		if (void 0 === response) return null;
		return response;
	}
	async getFeatureFlagPayloadsStateless(distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip, flagKeysToEvaluate) {
		await this._initPromise;
		return (await this.getFeatureFlagsAndPayloadsStateless(distinctId, groups, personProperties, groupProperties, disableGeoip, flagKeysToEvaluate)).payloads;
	}
	async getFeatureFlagsStateless(distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip, flagKeysToEvaluate) {
		await this._initPromise;
		return await this.getFeatureFlagsAndPayloadsStateless(distinctId, groups, personProperties, groupProperties, disableGeoip, flagKeysToEvaluate);
	}
	async getFeatureFlagsAndPayloadsStateless(distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip, flagKeysToEvaluate) {
		await this._initPromise;
		const featureFlagDetails = await this.getFeatureFlagDetailsStateless(distinctId, groups, personProperties, groupProperties, disableGeoip, flagKeysToEvaluate);
		if (!featureFlagDetails) return {
			flags: void 0,
			payloads: void 0,
			requestId: void 0
		};
		return {
			flags: featureFlagDetails.featureFlags,
			payloads: featureFlagDetails.featureFlagPayloads,
			requestId: featureFlagDetails.requestId
		};
	}
	async getFeatureFlagDetailsStateless(distinctId, groups = {}, personProperties = {}, groupProperties = {}, disableGeoip, flagKeysToEvaluate) {
		await this._initPromise;
		const extraPayload = { geoip_disable: disableGeoip ?? this.disableGeoip };
		if (flagKeysToEvaluate) extraPayload["flag_keys_to_evaluate"] = flagKeysToEvaluate;
		const result = await this.getFlags(distinctId, groups, personProperties, groupProperties, extraPayload);
		if (!result.success) return;
		const flagsResponse = result.response;
		if (flagsResponse.errorsWhileComputingFlags) console.error("[FEATURE FLAGS] Error while computing feature flags, some flags may be missing or incorrect. Learn more at https://posthog.com/docs/feature-flags/best-practices");
		if (flagsResponse.quotaLimited?.includes("feature_flags")) {
			console.warn("[FEATURE FLAGS] Feature flags quota limit exceeded - feature flags unavailable. Learn more about billing limits at https://posthog.com/docs/billing/limits-alerts");
			return {
				flags: {},
				featureFlags: {},
				featureFlagPayloads: {},
				requestId: flagsResponse?.requestId,
				quotaLimited: flagsResponse.quotaLimited
			};
		}
		return flagsResponse;
	}
	async getSurveysStateless() {
		await this._initPromise;
		if (this.disabled) return [];
		if (true === this.disableSurveys) {
			this._logger.info("Loading surveys is disabled.");
			return [];
		}
		const url = `${this.host}/api/surveys/?token=${this.apiKey}`;
		const fetchOptions = {
			method: "GET",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json"
			}
		};
		const newSurveys = (await this.fetchWithRetry(url, fetchOptions, {
			type: "required",
			consume: (response) => {
				if (200 !== response.status || !response.json) {
					const msg = `Surveys API could not be loaded: ${response.status}`;
					const error = new Error(msg);
					this._logger.error(error);
					this._events.emit("error", new Error(msg));
					return Promise.resolve(void 0);
				}
				return response.json();
			}
		}).catch((error) => {
			this._logger.error("Surveys API could not be loaded", error);
			this._events.emit("error", error);
		}))?.surveys;
		if (newSurveys) this._logger.info("Surveys fetched from API: ", JSON.stringify(newSurveys));
		return newSurveys ?? [];
	}
	get props() {
		if (!this._props) this._props = this.getPersistedProperty(types_PostHogPersistedProperty.Props);
		return this._props || {};
	}
	set props(val) {
		this._props = val;
	}
	async register(properties) {
		this.wrap(() => {
			this.props = {
				...this.props,
				...properties
			};
			this.setPersistedProperty(types_PostHogPersistedProperty.Props, this.props);
		});
	}
	async unregister(property) {
		this.wrap(() => {
			delete this.props[property];
			this.setPersistedProperty(types_PostHogPersistedProperty.Props, this.props);
		});
	}
	processBeforeEnqueue(message) {
		return message;
	}
	async flushStorage() {}
	getQueueRouteKey(_message) {
		return DEFAULT_QUEUE_ROUTE;
	}
	persistedQueueKeyForRoute(_route) {
		return types_PostHogPersistedProperty.Queue;
	}
	getActiveQueueRoutes() {
		return [DEFAULT_QUEUE_ROUTE];
	}
	getRouteQueue(route) {
		return this.getPersistedProperty(this.persistedQueueKeyForRoute(route)) || [];
	}
	enqueue(type, _message, options) {
		this.wrap(() => {
			if (this.optedOut) return void this._events.emit(type, "Library is disabled. Not sending event. To re-enable, call posthog.optIn()");
			let message = this.prepareMessage(_message, options);
			message = this.processBeforeEnqueue(message);
			if (null === message) return;
			message = this.normalizeMessage(message);
			const queueKey = this.persistedQueueKeyForRoute(this.getQueueRouteKey(message));
			const queue = this.getPersistedProperty(queueKey) || [];
			if (queue.length >= this.maxQueueSize) {
				queue.shift();
				this._logger.warn("Queue is full, the oldest event is dropped.");
			}
			queue.push({ message });
			this.setPersistedProperty(queueKey, queue);
			this._events.emit(type, message);
			if (queue.length >= this.flushAt) this.flushBackground();
			if (this.flushInterval && !this._flushTimer) this._flushTimer = safeSetTimeout(() => this.flushBackground(), this.flushInterval);
		});
	}
	async sendImmediate(type, _message, options) {
		if (this.disabled) return void this._logger.warn("The client is disabled");
		if (!this._isInitialized) await this._initPromise;
		if (this.optedOut) return void this._events.emit(type, "Library is disabled. Not sending event. To re-enable, call posthog.optIn()");
		let message = this.prepareMessage(_message, options);
		message = this.processBeforeEnqueue(message);
		if (null === message) return;
		message = this.normalizeMessage(message);
		try {
			await this.sendBatch([message], void 0, this.getQueueRouteKey(message));
		} catch (err) {
			this._events.emit("error", err);
		}
	}
	normalizeMessage(message) {
		const { type: _type, library, library_version, ...sanitizedMessage } = message;
		let properties = isPostHogEventProperties(sanitizedMessage.properties) ? sanitizedMessage.properties : void 0;
		if (void 0 !== library && properties?.$lib === void 0) properties = {
			...properties || {},
			$lib: library
		};
		if (void 0 !== library_version && properties?.$lib_version === void 0) properties = {
			...properties || {},
			$lib_version: library_version
		};
		if (properties) sanitizedMessage.properties = properties;
		sanitizedMessage.uuid = getEventUuid(sanitizedMessage.uuid, uuidv7);
		return sanitizedMessage;
	}
	prepareMessage(_message, options) {
		const message = {
			..._message,
			timestamp: options?.timestamp ? options?.timestamp : currentISOTime(),
			uuid: getEventUuid(options?.uuid, uuidv7)
		};
		if (options?.disableGeoip ?? this.disableGeoip) {
			if (!isPostHogEventProperties(message.properties)) message.properties = {};
			message.properties["$geoip_disable"] = true;
		}
		if (message.distinctId) {
			message.distinct_id = message.distinctId;
			delete message.distinctId;
		}
		return message;
	}
	clearFlushTimer() {
		if (this._flushTimer) {
			clearTimeout(this._flushTimer);
			this._flushTimer = void 0;
		}
	}
	flushBackground() {
		if (this.pendingFlushPromise) return;
		this.flush().catch(async (err) => {
			await logFlushError(err);
		});
	}
	async waitForPendingPromises(maxPromiseId, ignoredPromises = []) {
		const ignoredPendingPromises = ignoredPromises.filter((promise) => !!promise);
		let iteration = 0;
		while (true) {
			const promises = this.promiseQueue.getPromises([...ignoredPendingPromises, ...this.flushPromises], maxPromiseId);
			if (0 === promises.length) return;
			if (iteration > 0) this._logger.debug(`flush() re-checking ${promises.length} pending promise(s) before flushing`);
			await Promise.all(promises.map((promise) => promise.catch(() => {})));
			iteration++;
		}
	}
	flushWithPendingPromises() {
		return this.flushInternal(true);
	}
	flush() {
		return this.flushInternal(false);
	}
	flushInternal(waitForPendingPromises) {
		if (this.disabled) return Promise.resolve();
		if (!waitForPendingPromises && this.pendingFlushPromise) return this.pendingFlushPromise;
		const previousFlushPromise = this.flushPromise;
		const maxPromiseId = this.promiseQueue.maxId;
		const nextFlushPromise = Promise.resolve().then(() => {
			if (waitForPendingPromises) return this.waitForPendingPromises(maxPromiseId, [previousFlushPromise, nextFlushPromise]);
		}).then(() => allSettled([previousFlushPromise])).then(() => {
			if (this.pendingFlushPromise === nextFlushPromise) this.pendingFlushPromise = null;
			return this._flush();
		});
		this.pendingFlushPromise = nextFlushPromise;
		this.flushPromise = nextFlushPromise;
		this.flushPromises.add(nextFlushPromise);
		this.addPendingPromise(nextFlushPromise);
		allSettled([nextFlushPromise]).then(() => {
			this.flushPromises.delete(nextFlushPromise);
			if (this.pendingFlushPromise === nextFlushPromise) this.pendingFlushPromise = null;
			if (this.flushPromise === nextFlushPromise) this.flushPromise = null;
		});
		return nextFlushPromise;
	}
	getCustomHeaders() {
		const customUserAgent = this.getCustomUserAgent();
		const headers = {};
		if (customUserAgent && "" !== customUserAgent) headers["User-Agent"] = customUserAgent;
		return headers;
	}
	async sendBatch(batchMessages, retryOptions, _route = DEFAULT_QUEUE_ROUTE) {
		const data = {
			api_key: this.apiKey,
			batch: batchMessages,
			sent_at: currentISOTime()
		};
		if (this.historicalMigration) data.historical_migration = true;
		const payload = safeJsonStringify(data);
		const url = `${this.host}/batch/`;
		const gzippedPayload = this.disableCompression ? null : await gzipCompress(payload, this.isDebug);
		const fetchOptions = {
			method: "POST",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json",
				...null !== gzippedPayload && { "Content-Encoding": "gzip" }
			},
			body: gzippedPayload || payload
		};
		await this.fetchWithRetry(url, fetchOptions, { type: "successful-write" }, retryOptions);
	}
	async _flush() {
		this.clearFlushTimer();
		await this._initPromise;
		const routes = this.getActiveQueueRoutes();
		if (!routes.some((route) => this.getRouteQueue(route).length > 0)) return;
		const sentMessages = [];
		let firstError;
		for (const route of routes) try {
			await this._flushRoute(route, sentMessages);
		} catch (err) {
			if (void 0 === firstError) firstError = err;
		}
		if (void 0 !== firstError) throw firstError;
		this._events.emit("flush", sentMessages);
	}
	async _flushRoute(route, sentMessages) {
		const queueKey = this.persistedQueueKeyForRoute(route);
		let queue = this.getPersistedProperty(queueKey) || [];
		if (!queue.length) return;
		const originalQueueLength = queue.length;
		let sentFromRoute = 0;
		while (queue.length > 0 && sentFromRoute < originalQueueLength) {
			const batchItems = queue.slice(0, this.maxBatchSize);
			const batchMessages = batchItems.map((item) => void 0 === item.message ? item.message : this.normalizeMessage(item.message));
			const persistQueueChange = async () => {
				const refreshedQueue = this.getPersistedProperty(queueKey) || [];
				const remainingBatchItems = [...batchItems];
				const newQueue = refreshedQueue.filter((item) => {
					const itemUuid = item.message?.uuid;
					const batchItemIndex = remainingBatchItems.findIndex((batchItem) => batchItem === item || "string" == typeof itemUuid && itemUuid.length > 0 && batchItem.message?.uuid === itemUuid);
					if (-1 === batchItemIndex) return true;
					remainingBatchItems.splice(batchItemIndex, 1);
					return false;
				});
				this.setPersistedProperty(queueKey, newQueue);
				queue = newQueue;
				this._dequeuedMessagesCount += batchItems.length;
				await this.flushStorage();
			};
			const retryOptions = { retryCheck: (err) => {
				if (isPostHogFetchContentTooLargeError(err)) return false;
				return isPostHogFetchRetryableError(err);
			} };
			try {
				await this.sendBatch(batchMessages, retryOptions, route);
			} catch (err) {
				if (isPostHogFetchContentTooLargeError(err) && batchMessages.length > 1) {
					this.maxBatchSize = Math.max(1, Math.floor(batchMessages.length / 2));
					this._logger.warn(`Received 413 when sending batch of size ${batchMessages.length}, reducing batch size to ${this.maxBatchSize}`);
					continue;
				}
				if (!(err instanceof PostHogFetchNetworkError)) await persistQueueChange();
				this._events.emit("error", err);
				throw err;
			}
			await persistQueueChange();
			sentMessages.push(...batchMessages);
			sentFromRoute += batchMessages.length;
		}
	}
	async _sendLogsBatch(payload) {
		if (this.disabled) return {
			kind: "fatal",
			error: /* @__PURE__ */ new Error("The client is disabled")
		};
		const serialized = JSON.stringify(payload);
		const url = `${this.host}/i/v1/logs?token=${encodeURIComponent(this.apiKey)}`;
		const gzippedPayload = this.disableCompression ? null : await gzipCompress(serialized, this.isDebug);
		const fetchOptions = {
			method: "POST",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json",
				...null !== gzippedPayload && { "Content-Encoding": "gzip" }
			},
			body: gzippedPayload || serialized
		};
		try {
			await this.fetchWithRetry(url, fetchOptions, { type: "successful-write" }, { retryCheck: (err) => {
				if (isPostHogFetchContentTooLargeError(err)) return false;
				return isPostHogFetchRetryableError(err);
			} });
			return { kind: "ok" };
		} catch (err) {
			if (isPostHogFetchContentTooLargeError(err)) return { kind: "too-large" };
			if (err instanceof PostHogFetchNetworkError) return {
				kind: "retry-later",
				error: err
			};
			return {
				kind: "fatal",
				error: err
			};
		}
	}
	async _sendMetricsBatch(payload) {
		if (this.disabled) return {
			kind: "fatal",
			error: /* @__PURE__ */ new Error("The client is disabled")
		};
		const serialized = JSON.stringify(payload);
		const url = `${this.host}/i/v1/metrics?token=${encodeURIComponent(this.apiKey)}`;
		const gzippedPayload = this.disableCompression ? null : await gzipCompress(serialized, this.isDebug);
		const fetchOptions = {
			method: "POST",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json",
				...null !== gzippedPayload && { "Content-Encoding": "gzip" }
			},
			body: gzippedPayload || serialized
		};
		try {
			await this.fetchWithRetry(url, fetchOptions, { type: "successful-write" }, { retryCheck: (err) => {
				if (isPostHogFetchContentTooLargeError(err)) return false;
				return isPostHogFetchRetryableError(err);
			} });
			return { kind: "ok" };
		} catch (err) {
			if (isPostHogFetchContentTooLargeError(err)) return { kind: "too-large" };
			if (isPostHogFetchRetryableError(err)) return {
				kind: "retry-later",
				error: err
			};
			return {
				kind: "fatal",
				error: err
			};
		}
	}
	async fetchWithRetry(url, options, responseHandling, retryOptions, requestTimeout) {
		const body = options.body ? options.body : "";
		let reqByteLength = -1;
		try {
			reqByteLength = body instanceof Blob ? body.size : Buffer.byteLength(body, "utf8");
		} catch {
			if (body instanceof Blob) reqByteLength = body.size;
			else reqByteLength = new TextEncoder().encode(body).length;
		}
		const retriableOptions = {
			...this._retryOptions,
			...retryOptions
		};
		let attempt = 0;
		return await retriable(async () => {
			attempt++;
			const ctrl = new AbortController();
			const timeoutMs = requestTimeout ?? this.requestTimeout;
			const requestDeadline = Date.now() + timeoutMs;
			let timer;
			const deadline = new Promise((_resolve, reject) => {
				timer = safeSetTimeout(() => {
					const timeoutError = /* @__PURE__ */ new Error(`Request timed out after ${timeoutMs}ms`);
					timeoutError.name = "AbortError";
					reject(timeoutError);
					ctrl.abort(timeoutError);
				}, timeoutMs);
			});
			let res;
			let responseAccepted = false;
			let cancellation;
			const cancelBody = () => cancellation ??= (async () => {
				try {
					await res?.body?.cancel();
				} catch {}
			})();
			try {
				let fetchPromise;
				try {
					fetchPromise = this.fetch(url, {
						signal: ctrl.signal,
						...options
					});
				} catch (e) {
					throw new PostHogFetchNetworkError(e);
				}
				fetchPromise.then((lateResponse) => {
					if (ctrl.signal.aborted && !responseAccepted) Promise.resolve(lateResponse.body?.cancel()).catch(() => {});
				}).catch(() => {});
				try {
					res = await Promise.race([fetchPromise, deadline]);
					responseAccepted = true;
				} catch (e) {
					throw new PostHogFetchNetworkError(e);
				}
				if (!("no-cors" === options.mode) && (res.status < 200 || res.status >= 400)) throw new PostHogFetchHttpError(res, reqByteLength, requestDeadline, ctrl);
				if ("successful-write" === responseHandling.type) {
					try {
						await Promise.race([cancelBody(), deadline]);
					} catch {}
					return;
				}
				try {
					return await Promise.race([responseHandling.consume(res), deadline]);
				} catch (e) {
					if (ctrl.signal.aborted) throw new PostHogFetchNetworkError(e);
					throw e;
				}
			} finally {
				clearTimeout(timer);
				if (ctrl.signal.aborted && res) cancelBody();
			}
		}, {
			...retriableOptions,
			retryCheck: (error) => {
				const shouldRetry = retriableOptions.retryCheck(error);
				if (shouldRetry && attempt <= retriableOptions.retryCount && error instanceof PostHogFetchHttpError) error.cancelResponseBody();
				return shouldRetry;
			}
		});
	}
	async _shutdown(shutdownTimeoutMs = 3e4) {
		await this._initPromise;
		let hasTimedOut = false;
		this.clearFlushTimer();
		if (this.disabled) return;
		const doShutdown = async () => {
			try {
				await this.promiseQueue.join();
				while (true) {
					if (!this.getActiveQueueRoutes().some((route) => this.getRouteQueue(route).length > 0)) break;
					const dequeuedBeforeFlush = this._dequeuedMessagesCount;
					await this.flush();
					if (hasTimedOut) break;
					if (this._dequeuedMessagesCount === dequeuedBeforeFlush) {
						this._logger.warn("Shutdown flush completed but did not send any queued events. Stopping drain to avoid a loop.");
						break;
					}
				}
			} catch (e) {
				if (!isPostHogFetchError(e)) throw e;
				await logFlushError(e);
			}
		};
		return raceWithTimeout(doShutdown(), shutdownTimeoutMs, () => {
			this._logger.error("Timed out while shutting down PostHog");
			hasTimedOut = true;
			throw "Timeout while shutting down PostHog. Some events may not have been sent.";
		});
	}
	async shutdown(shutdownTimeoutMs = 3e4) {
		if (this.shutdownPromise) this._logger.warn("shutdown() called while already shutting down. shutdown() is meant to be called once before process exit - use flush() for per-request cleanup");
		else this.shutdownPromise = this._shutdown(shutdownTimeoutMs).finally(() => {
			this.shutdownPromise = null;
		});
		return this.shutdownPromise;
	}
};
//#endregion
export { gzipCompress as C, isBlockedUA as S, minimizeFlagCalledEventProperties as T, BucketedRateLimiter as _, EventCoercer as a, isPlainObject as b, ErrorCoercer as c, ErrorPropertiesBuilder as d, PostHogMetrics as f, uuidv7 as g, safeSetTimeout as h, PrimitiveCoercer as i, createStackParser as l, raceWithTimeout as m, getInjectedReleaseId as n, ObjectCoercer as o, resolveMetricsConfig as p, ReduceableCache as r, StringCoercer as s, PostHogCoreStateless as t, nodeStackLineParser as u, resolveExceptionRateLimiterConfig as v, types_PostHogPersistedProperty as w, safeJsonStringify as x, isObject as y };
