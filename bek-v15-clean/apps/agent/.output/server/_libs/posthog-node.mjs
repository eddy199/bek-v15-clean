import { fileURLToPath as __eveFileURLToPath } from "node:url";
import { dirname as __eveDirname } from "node:path";
const __filename = __eveFileURLToPath(import.meta.url);
__eveDirname(__filename);
import { C as gzipCompress, S as isBlockedUA, T as minimizeFlagCalledEventProperties, _ as BucketedRateLimiter, a as EventCoercer, b as isPlainObject, c as ErrorCoercer, d as ErrorPropertiesBuilder, f as PostHogMetrics, g as uuidv7, h as safeSetTimeout, i as PrimitiveCoercer, l as createStackParser, m as raceWithTimeout, n as getInjectedReleaseId, o as ObjectCoercer, p as resolveMetricsConfig, r as ReduceableCache, s as StringCoercer, t as PostHogCoreStateless, u as nodeStackLineParser, v as resolveExceptionRateLimiterConfig, w as types_PostHogPersistedProperty, x as safeJsonStringify, y as isObject } from "./posthog__core.mjs";
import { constants } from "node:fs";
import { isAbsolute } from "node:path";
import { AsyncLocalStorage } from "node:async_hooks";
import { dirname as dirname$1, isAbsolute as isAbsolute$1, posix as posix$1, relative as relative$1, sep as sep$1 } from "path";
import { open } from "node:fs/promises";
import { createInterface } from "node:readline";
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/error-tracking/modifiers/module.node.mjs
function createModulerModifier() {
	const getModuleFromFileName = createGetModuleFromFilename();
	return async (frames) => {
		for (const frame of frames) frame.module = getModuleFromFileName(frame.filename);
		return frames;
	};
}
function createGetModuleFromFilename(basePath = process.argv[1] ? dirname$1(process.argv[1]) : process.cwd(), isWindows = "\\" === sep$1) {
	const normalizedBase = isWindows ? normalizeWindowsPath(basePath) : basePath;
	return (filename) => {
		if (!filename) return;
		const normalizedFilename = isWindows ? normalizeWindowsPath(filename) : filename;
		let { dir, base: file, ext } = posix$1.parse(normalizedFilename);
		if (".js" === ext || ".mjs" === ext || ".cjs" === ext) file = file.slice(0, -1 * ext.length);
		const decodedFile = decodeURIComponent(file);
		if (!dir) dir = ".";
		const n = dir.lastIndexOf("/node_modules");
		if (n > -1) return `${dir.slice(n + 14).replace(/\//g, ".")}:${decodedFile}`;
		if (dir.startsWith(normalizedBase)) {
			const moduleName = dir.slice(normalizedBase.length + 1).replace(/\//g, ".");
			return moduleName ? `${moduleName}:${decodedFile}` : decodedFile;
		}
		return decodedFile;
	};
}
function normalizeWindowsPath(path) {
	return path.replace(/^[A-Z]:/, "").replace(/\\/g, "/");
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/error-tracking/modifiers/context-lines.node.mjs
const LRU_FILE_CONTENTS_CACHE = new ReduceableCache(25);
const LRU_FILE_CONTENTS_FS_READ_FAILED = new ReduceableCache(20);
const DEFAULT_LINES_OF_CONTEXT = 7;
async function addSourceContext(frames, openSourceFile = open, logger) {
	const filesToLines = {};
	let basePath;
	try {
		basePath = process.cwd();
	} catch {}
	for (let i = frames.length - 1; i >= 0; i--) {
		const frame = frames[i];
		const filename = frame?.filename;
		if (!frame || "string" != typeof filename || "number" != typeof frame.lineno || shouldSkipContextLinesForFile(filename) || shouldSkipContextLinesForFrame(frame)) continue;
		if (!isAbsolute(filename) && void 0 === basePath) continue;
		if (!filesToLines[filename]) filesToLines[filename] = [];
		filesToLines[filename].push(frame.lineno);
	}
	const files = Object.keys(filesToLines);
	if (0 == files.length) return frames;
	const readlinePromises = [];
	for (const file of files) {
		const cacheKey = makeSourceCacheKey(file, basePath);
		if (void 0 === cacheKey) continue;
		if (LRU_FILE_CONTENTS_FS_READ_FAILED.get(cacheKey)) continue;
		const filesToLineRanges = filesToLines[file];
		if (!filesToLineRanges) continue;
		filesToLineRanges.sort((a, b) => a - b);
		const ranges = makeLineReaderRanges(filesToLineRanges);
		if (ranges.every((r) => rangeExistsInContentCache(cacheKey, r))) continue;
		const cache = emplace(LRU_FILE_CONTENTS_CACHE, cacheKey, {});
		readlinePromises.push(getContextLinesFromFile(file, ranges, cache, cacheKey, openSourceFile, logger));
	}
	await Promise.all(readlinePromises).catch(() => {});
	if (frames && frames.length > 0) addSourceContextToFrames(frames, LRU_FILE_CONTENTS_CACHE, basePath);
	LRU_FILE_CONTENTS_CACHE.reduce();
	return frames;
}
async function openRegularSourceFile(path, openSourceFile, logger) {
	let fileHandle;
	let isValid = false;
	try {
		fileHandle = await openSourceFile(path, constants.O_RDONLY | constants.O_NONBLOCK);
		const fileStat = await fileHandle.stat();
		if (!fileStat.isFile()) return;
		if (fileStat.size > 10485760) return void logger?.debug(`Skipping source context for oversized file ${path}: ${fileStat.size} bytes exceeds 10485760`);
		isValid = true;
		return fileHandle;
	} catch {
		return;
	} finally {
		if (fileHandle && !isValid) await fileHandle.close().catch(() => {});
	}
}
async function getContextLinesFromFile(path, ranges, output, cacheKey, openSourceFile, logger) {
	const fileHandle = await openRegularSourceFile(path, openSourceFile, logger);
	if (void 0 === fileHandle) return void LRU_FILE_CONTENTS_FS_READ_FAILED.set(cacheKey, 1);
	const openedFileHandle = fileHandle;
	return new Promise((resolve) => {
		let finished = false;
		function destroyStreamAndResolve(stream) {
			if (finished) return;
			finished = true;
			stream?.destroy();
			openedFileHandle.close().then(resolve, resolve);
		}
		let stream;
		try {
			stream = openedFileHandle.createReadStream({
				autoClose: false,
				start: 0,
				end: 10485759
			});
		} catch {
			LRU_FILE_CONTENTS_FS_READ_FAILED.set(cacheKey, 1);
			destroyStreamAndResolve();
			return;
		}
		let lineReaded;
		try {
			lineReaded = createInterface({ input: stream });
		} catch {
			LRU_FILE_CONTENTS_FS_READ_FAILED.set(cacheKey, 1);
			destroyStreamAndResolve(stream);
			return;
		}
		let lineNumber = 0;
		let currentRangeIndex = 0;
		const range = ranges[currentRangeIndex];
		if (void 0 === range) return void destroyStreamAndResolve(stream);
		let rangeStart = range[0];
		let rangeEnd = range[1];
		function onStreamError() {
			LRU_FILE_CONTENTS_FS_READ_FAILED.set(cacheKey, 1);
			lineReaded.close();
			lineReaded.removeAllListeners();
			destroyStreamAndResolve(stream);
		}
		stream.on("error", onStreamError);
		lineReaded.on("error", onStreamError);
		lineReaded.on("close", () => destroyStreamAndResolve(stream));
		lineReaded.on("line", (line) => {
			lineNumber++;
			if (lineNumber < rangeStart) return;
			output[lineNumber] = snipLine(line, 0);
			if (lineNumber >= rangeEnd) {
				if (currentRangeIndex === ranges.length - 1) {
					lineReaded.close();
					lineReaded.removeAllListeners();
					return;
				}
				currentRangeIndex++;
				const range = ranges[currentRangeIndex];
				if (void 0 === range) {
					lineReaded.close();
					lineReaded.removeAllListeners();
					return;
				}
				rangeStart = range[0];
				rangeEnd = range[1];
			}
		});
	});
}
function addSourceContextToFrames(frames, cache, basePath) {
	for (const frame of frames) if (frame.filename && void 0 === frame.context_line && "number" == typeof frame.lineno) {
		const cacheKey = makeSourceCacheKey(frame.filename, basePath);
		const contents = void 0 === cacheKey ? void 0 : cache.get(cacheKey);
		if (void 0 === contents) continue;
		addContextToFrame(frame.lineno, frame, contents);
	}
}
function addContextToFrame(lineno, frame, contents) {
	if (void 0 === frame.lineno || void 0 === contents) return;
	frame.pre_context = [];
	for (let i = makeRangeStart(lineno); i < lineno; i++) {
		const line = contents[i];
		if (void 0 === line) return void clearLineContext(frame);
		frame.pre_context.push(line);
	}
	if (void 0 === contents[lineno]) return void clearLineContext(frame);
	frame.context_line = contents[lineno];
	const end = makeRangeEnd(lineno);
	frame.post_context = [];
	for (let i = lineno + 1; i <= end; i++) {
		const line = contents[i];
		if (void 0 === line) break;
		frame.post_context.push(line);
	}
}
function clearLineContext(frame) {
	delete frame.pre_context;
	delete frame.context_line;
	delete frame.post_context;
}
function shouldSkipContextLinesForFile(path) {
	return path.startsWith("node:") || path.endsWith(".min.js") || path.endsWith(".min.cjs") || path.endsWith(".min.mjs") || path.startsWith("data:");
}
function shouldSkipContextLinesForFrame(frame) {
	if (void 0 !== frame.lineno && frame.lineno > 1e4) return true;
	if (void 0 !== frame.colno && frame.colno > 1e3) return true;
	return false;
}
function makeSourceCacheKey(path, basePath) {
	if (isAbsolute(path)) return JSON.stringify([null, path]);
	return void 0 === basePath ? void 0 : JSON.stringify([basePath, path]);
}
function rangeExistsInContentCache(cacheKey, range) {
	const contents = LRU_FILE_CONTENTS_CACHE.get(cacheKey);
	if (void 0 === contents) return false;
	for (let i = range[0]; i <= range[1]; i++) if (void 0 === contents[i]) return false;
	return true;
}
function makeLineReaderRanges(lines) {
	if (!lines.length) return [];
	let i = 0;
	const line = lines[0];
	if ("number" != typeof line) return [];
	let current = makeContextRange(line);
	const out = [];
	while (true) {
		if (i === lines.length - 1) {
			out.push(current);
			break;
		}
		const next = lines[i + 1];
		if ("number" != typeof next) break;
		if (next <= current[1]) current[1] = next + DEFAULT_LINES_OF_CONTEXT;
		else {
			out.push(current);
			current = makeContextRange(next);
		}
		i++;
	}
	return out;
}
function makeContextRange(line) {
	return [makeRangeStart(line), makeRangeEnd(line)];
}
function makeRangeStart(line) {
	return Math.max(1, line - DEFAULT_LINES_OF_CONTEXT);
}
function makeRangeEnd(line) {
	return line + DEFAULT_LINES_OF_CONTEXT;
}
function emplace(map, key, contents) {
	const value = map.get(key);
	if (void 0 === value) {
		map.set(key, contents);
		return contents;
	}
	return value;
}
function snipLine(line, colno) {
	let newLine = line;
	const lineLength = newLine.length;
	if (lineLength <= 150) return newLine;
	if (colno > lineLength) colno = lineLength;
	let start = Math.max(colno - 60, 0);
	if (start < 5) start = 0;
	let end = Math.min(start + 140, lineLength);
	if (end > lineLength - 5) end = lineLength;
	if (end === lineLength) start = Math.max(end - 140, 0);
	newLine = newLine.slice(start, end);
	if (start > 0) newLine = `...${newLine}`;
	if (end < lineLength) newLine += "...";
	return newLine;
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/error-tracking/modifiers/relative-path.node.mjs
function createRelativePathModifier(basePath = process.cwd()) {
	const isWindows = "\\" === sep$1;
	const toUnix = (p) => isWindows ? p.replace(/\\/g, "/") : p;
	const normalizedBase = toUnix(basePath);
	return async (frames) => {
		for (const frame of frames) if (!(!frame.filename || frame.filename.startsWith("node:") || frame.filename.startsWith("data:"))) {
			if (isAbsolute$1(frame.filename)) frame.filename = toUnix(relative$1(normalizedBase, toUnix(frame.filename)));
		}
		return frames;
	};
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/types.mjs
const FeatureFlagError = {
	ERRORS_WHILE_COMPUTING: "errors_while_computing_flags",
	FLAG_MISSING: "flag_missing",
	QUOTA_LIMITED: "quota_limited",
	UNKNOWN_ERROR: "unknown_error"
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/feature-flag-evaluations.mjs
var FeatureFlagEvaluations = class FeatureFlagEvaluations {
	constructor(init) {
		this._host = init.host;
		this._distinctId = init.distinctId;
		this._groups = init.groups;
		this._disableGeoip = init.disableGeoip;
		this._flags = init.flags;
		this._requestId = init.requestId;
		this._evaluatedAt = init.evaluatedAt;
		this._flagDefinitionsLoadedAt = init.flagDefinitionsLoadedAt;
		this._errorsWhileComputing = init.errorsWhileComputing ?? false;
		this._quotaLimited = init.quotaLimited ?? false;
		this._accessed = init.accessed ?? /* @__PURE__ */ new Set();
		this._isSlice = init.isSlice ?? false;
	}
	isEnabled(key) {
		const flag = this._flags[key];
		this._recordAccess(key);
		return flag?.enabled ?? false;
	}
	getFlag(key) {
		const flag = this._flags[key];
		this._recordAccess(key);
		if (!flag) return;
		if (!flag.enabled) return false;
		return flag.variant ?? true;
	}
	getFlagPayload(key) {
		return this._flags[key]?.payload;
	}
	onlyAccessed() {
		const filtered = {};
		for (const key of this._accessed) {
			const flag = this._flags[key];
			if (flag) filtered[key] = flag;
		}
		return this._cloneWith(filtered);
	}
	only(keys) {
		const filtered = {};
		const missing = [];
		for (const key of keys) {
			const flag = this._flags[key];
			if (flag) filtered[key] = flag;
			else missing.push(key);
		}
		if (missing.length > 0) this._host.logWarning(`FeatureFlagEvaluations.only() was called with flag keys that are not in the evaluation set and will be dropped: ${missing.join(", ")}`);
		return this._cloneWith(filtered);
	}
	get keys() {
		return Object.keys(this._flags);
	}
	_getEventProperties() {
		const properties = {};
		const activeFlags = [];
		for (const [key, flag] of Object.entries(this._flags)) {
			const value = false === flag.enabled ? false : flag.variant ?? true;
			properties[`$feature/${key}`] = value;
			if (flag.enabled) activeFlags.push(key);
		}
		if (activeFlags.length > 0) {
			activeFlags.sort();
			properties["$active_feature_flags"] = activeFlags;
		}
		return properties;
	}
	_cloneWith(flags) {
		return new FeatureFlagEvaluations({
			host: this._host,
			distinctId: this._distinctId,
			groups: this._groups,
			disableGeoip: this._disableGeoip,
			flags,
			requestId: this._requestId,
			evaluatedAt: this._evaluatedAt,
			flagDefinitionsLoadedAt: this._flagDefinitionsLoadedAt,
			errorsWhileComputing: this._errorsWhileComputing,
			quotaLimited: this._quotaLimited,
			accessed: new Set(this._accessed),
			isSlice: true
		});
	}
	_recordAccess(key) {
		this._accessed.add(key);
		if ("" === this._distinctId) return;
		if (this._isSlice && !(key in this._flags)) return;
		const flag = this._flags[key];
		const response = void 0 === flag ? void 0 : false === flag.enabled ? false : flag.variant ?? true;
		const properties = {
			$feature_flag: key,
			$feature_flag_response: response,
			$feature_flag_id: flag?.id,
			$feature_flag_version: flag?.version,
			$feature_flag_reason: flag?.reason,
			locally_evaluated: flag?.locallyEvaluated ?? false,
			[`$feature/${key}`]: response,
			$feature_flag_request_id: this._requestId,
			$feature_flag_evaluated_at: flag?.locallyEvaluated ? Date.now() : this._evaluatedAt
		};
		if (flag?.hasExperiment !== void 0) properties.$feature_flag_has_experiment = flag.hasExperiment;
		if (flag?.locallyEvaluated && void 0 !== this._flagDefinitionsLoadedAt) properties.$feature_flag_definitions_loaded_at = this._flagDefinitionsLoadedAt;
		const errors = [];
		if (this._errorsWhileComputing) errors.push(FeatureFlagError.ERRORS_WHILE_COMPUTING);
		if (this._quotaLimited) errors.push(FeatureFlagError.QUOTA_LIMITED);
		if (void 0 === flag) errors.push(FeatureFlagError.FLAG_MISSING);
		if (errors.length > 0) properties.$feature_flag_error = errors.join(",");
		this._host.captureFlagCalledEventIfNeeded({
			distinctId: this._distinctId,
			key,
			response,
			groups: this._groups,
			disableGeoip: this._disableGeoip,
			properties
		});
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/feature-flags/crypto.mjs
async function hashSHA1(text) {
	const subtle = globalThis.crypto?.subtle;
	if (!subtle) throw new Error("SubtleCrypto API not available");
	const hashBuffer = await subtle.digest("SHA-1", new TextEncoder().encode(text));
	return Array.from(new Uint8Array(hashBuffer)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/feature-flags/feature-flags.mjs
const SIXTY_SECONDS = 6e4;
const LONG_SCALE = 0x1000000000000000;
const NULL_VALUES_ALLOWED_OPERATORS = ["is_not", "is_set"];
var ClientError = class ClientError extends Error {
	constructor(message) {
		super();
		Error.captureStackTrace(this, this.constructor);
		this.name = "ClientError";
		this.message = message;
		Object.setPrototypeOf(this, ClientError.prototype);
	}
};
function setCustomErrorPrototype(error, constructor) {
	error.name = constructor.name;
	Error.captureStackTrace(error, constructor);
	Object.setPrototypeOf(error, constructor.prototype);
}
var InconclusiveMatchError = class InconclusiveMatchError extends Error {
	constructor(message) {
		super(message);
		setCustomErrorPrototype(this, InconclusiveMatchError);
	}
};
var RequiresServerEvaluation = class RequiresServerEvaluation extends Error {
	constructor(message) {
		super(message);
		setCustomErrorPrototype(this, RequiresServerEvaluation);
	}
};
var FeatureFlagsPoller = class {
	constructor({ pollingInterval, personalApiKey, projectApiKey, timeout, host, customHeaders, ...options }) {
		this.debugMode = false;
		this.shouldBeginExponentialBackoff = false;
		this.backOffCount = 0;
		this.pollerStopped = false;
		this.pollingInterval = pollingInterval;
		this.personalApiKey = personalApiKey;
		this.featureFlags = [];
		this.featureFlagsByKey = {};
		this.groupTypeMapping = {};
		this.cohorts = {};
		this.loadedSuccessfullyOnce = false;
		this.timeout = timeout;
		this.projectApiKey = projectApiKey;
		this.host = host;
		this.poller = void 0;
		this.fetch = options.fetch || fetch;
		this.onError = options.onError;
		this.customHeaders = customHeaders;
		this.onLoad = options.onLoad;
		this.onMinimalFlagCalledEvents = options.onMinimalFlagCalledEvents;
		this.cacheProvider = options.cacheProvider;
		this.strictLocalEvaluation = options.strictLocalEvaluation ?? false;
		this.loadFeatureFlags();
	}
	debug(enabled = true) {
		this.debugMode = enabled;
	}
	logMsgIfDebug(fn) {
		if (this.debugMode) fn();
	}
	createEvaluationContext(distinctId, groups = {}, personProperties = {}, groupProperties = {}, evaluationCache = {}) {
		return {
			distinctId,
			groups,
			personProperties,
			groupProperties,
			evaluationCache
		};
	}
	async getFeatureFlag(key, distinctId, groups = {}, personProperties = {}, groupProperties = {}) {
		await this.loadFeatureFlags();
		let response;
		let featureFlag;
		if (!this.loadedSuccessfullyOnce) return response;
		featureFlag = this.featureFlagsByKey[key];
		if (void 0 !== featureFlag) {
			const evaluationContext = this.createEvaluationContext(distinctId, groups, personProperties, groupProperties);
			try {
				response = (await this.computeFlagAndPayloadLocally(featureFlag, evaluationContext)).value;
				this.logMsgIfDebug(() => console.debug(`Successfully computed flag locally: ${key} -> ${response}`));
			} catch (e) {
				if (e instanceof RequiresServerEvaluation || e instanceof InconclusiveMatchError) this.logMsgIfDebug(() => console.debug(`${e.name} when computing flag locally: ${key}: ${e.message}`));
				else if (e instanceof Error) this.onError?.(/* @__PURE__ */ new Error(`Error computing flag locally: ${key}: ${e}`));
			}
		}
		return response;
	}
	async getAllFlagsAndPayloads(evaluationContext, flagKeysToExplicitlyEvaluate) {
		await this.loadFeatureFlags();
		const response = {};
		const payloads = {};
		let fallbackToFlags = 0 == this.featureFlags.length;
		const flagsToEvaluate = flagKeysToExplicitlyEvaluate ? flagKeysToExplicitlyEvaluate.map((key) => this.featureFlagsByKey[key]).filter(Boolean) : this.featureFlags;
		const sharedEvaluationContext = {
			...evaluationContext,
			evaluationCache: evaluationContext.evaluationCache ?? {}
		};
		await Promise.all(flagsToEvaluate.map(async (flag) => {
			try {
				const { value: matchValue, payload: matchPayload } = await this.computeFlagAndPayloadLocally(flag, sharedEvaluationContext);
				response[flag.key] = matchValue;
				if (matchPayload) payloads[flag.key] = matchPayload;
			} catch (e) {
				if (e instanceof RequiresServerEvaluation || e instanceof InconclusiveMatchError) this.logMsgIfDebug(() => console.debug(`${e.name} when computing flag locally: ${flag.key}: ${e.message}`));
				else if (e instanceof Error) this.onError?.(/* @__PURE__ */ new Error(`Error computing flag locally: ${flag.key}: ${e}`));
				fallbackToFlags = true;
			}
		}));
		return {
			response,
			payloads,
			fallbackToFlags
		};
	}
	async computeFlagAndPayloadLocally(flag, evaluationContext, options = {}) {
		const { matchValue, skipLoadCheck = false } = options;
		if (!skipLoadCheck) await this.loadFeatureFlags();
		if (!this.loadedSuccessfullyOnce) return {
			value: false,
			payload: null
		};
		let flagValue;
		flagValue = void 0 !== matchValue ? matchValue : await this.computeFlagValueLocally(flag, evaluationContext);
		const payload = this.getFeatureFlagPayload(flag.key, flagValue);
		return {
			value: flagValue,
			payload
		};
	}
	async computeFlagValueLocally(flag, evaluationContext) {
		const { distinctId, groups, personProperties, groupProperties } = evaluationContext;
		if (!flag.active) return false;
		if (flag.ensure_experience_continuity) throw new InconclusiveMatchError("Flag has experience continuity enabled");
		const aggregation_group_type_index = (flag.filters || {}).aggregation_group_type_index;
		if (void 0 != aggregation_group_type_index) {
			const groupName = this.groupTypeMapping[String(aggregation_group_type_index)];
			if (!groupName) {
				this.logMsgIfDebug(() => console.warn(`[FEATURE FLAGS] Unknown group type index ${aggregation_group_type_index} for feature flag ${flag.key}`));
				throw new InconclusiveMatchError("Flag has unknown group type index");
			}
			if (!(groupName in groups)) {
				this.logMsgIfDebug(() => console.warn(`[FEATURE FLAGS] Can't compute group feature flag: ${flag.key} without group names passed in`));
				return false;
			}
			if ("device_id" === flag.bucketing_identifier && (personProperties?.$device_id === void 0 || personProperties?.$device_id === null || personProperties?.$device_id === "")) this.logMsgIfDebug(() => console.warn(`[FEATURE FLAGS] Ignoring bucketing_identifier for group flag: ${flag.key}`));
			const focusedGroupProperties = groupProperties[groupName];
			return await this.matchFeatureFlagProperties(flag, groups[groupName], focusedGroupProperties, evaluationContext);
		}
		{
			const bucketingValue = this.getBucketingValueForFlag(flag, distinctId, personProperties);
			if (void 0 === bucketingValue) {
				this.logMsgIfDebug(() => console.warn(`[FEATURE FLAGS] Can't compute feature flag: ${flag.key} without $device_id, falling back to server evaluation`));
				throw new InconclusiveMatchError(`Can't compute feature flag: ${flag.key} without $device_id`);
			}
			return await this.matchFeatureFlagProperties(flag, bucketingValue, personProperties, evaluationContext);
		}
	}
	getBucketingValueForFlag(flag, distinctId, properties) {
		if (flag.filters?.aggregation_group_type_index != void 0) return distinctId;
		if ("device_id" === flag.bucketing_identifier) {
			const deviceId = properties?.$device_id;
			if (null == deviceId || "" === deviceId) return;
			return deviceId;
		}
		return distinctId;
	}
	getFeatureFlagPayload(key, flagValue) {
		let payload = null;
		if (false !== flagValue && null != flagValue) {
			if ("boolean" == typeof flagValue) payload = this.featureFlagsByKey?.[key]?.filters?.payloads?.[flagValue.toString()] || null;
			else if ("string" == typeof flagValue) payload = this.featureFlagsByKey?.[key]?.filters?.payloads?.[flagValue] || null;
			if (null != payload) {
				if ("object" == typeof payload) return payload;
				if ("string" == typeof payload) try {
					return JSON.parse(payload);
				} catch {}
				return payload;
			}
		}
		return null;
	}
	async evaluateFlagDependency(property, properties, evaluationContext) {
		const { evaluationCache } = evaluationContext;
		const targetFlagKey = property.key;
		if (!this.featureFlagsByKey) throw new InconclusiveMatchError("Feature flags not available for dependency evaluation");
		if (!("dependency_chain" in property)) throw new InconclusiveMatchError(`Flag dependency property for '${targetFlagKey}' is missing required 'dependency_chain' field`);
		const dependencyChain = property.dependency_chain;
		if (!Array.isArray(dependencyChain)) throw new InconclusiveMatchError(`Flag dependency property for '${targetFlagKey}' has an invalid 'dependency_chain' (expected array, got ${typeof dependencyChain})`);
		if (0 === dependencyChain.length) throw new InconclusiveMatchError(`Circular dependency detected for flag '${targetFlagKey}' (empty dependency chain)`);
		for (const depFlagKey of dependencyChain) {
			if (!(depFlagKey in evaluationCache)) {
				const depFlag = this.featureFlagsByKey[depFlagKey];
				if (depFlag) if (depFlag.active) try {
					evaluationCache[depFlagKey] = await this.computeFlagValueLocally(depFlag, evaluationContext);
				} catch (error) {
					throw new InconclusiveMatchError(`Error evaluating flag dependency '${depFlagKey}' for flag '${targetFlagKey}': ${error}`);
				}
				else evaluationCache[depFlagKey] = false;
				else throw new InconclusiveMatchError(`Missing flag dependency '${depFlagKey}' for flag '${targetFlagKey}'`);
			}
			if (null == evaluationCache[depFlagKey]) throw new InconclusiveMatchError(`Dependency '${depFlagKey}' could not be evaluated`);
		}
		const targetFlagValue = evaluationCache[targetFlagKey];
		return this.flagEvaluatesToExpectedValue(property.value, targetFlagValue);
	}
	flagEvaluatesToExpectedValue(expectedValue, flagValue) {
		if ("boolean" == typeof expectedValue) return expectedValue === flagValue || "string" == typeof flagValue && "" !== flagValue && true === expectedValue;
		if ("string" == typeof expectedValue) return flagValue === expectedValue;
		return false;
	}
	async matchFeatureFlagProperties(flag, bucketingValue, properties, evaluationContext) {
		const flagFilters = flag.filters || {};
		const flagConditions = flagFilters.groups || [];
		const flagAggregation = flagFilters.aggregation_group_type_index;
		const earlyExitEnabled = flagFilters.early_exit ?? false;
		const { groups, groupProperties } = evaluationContext;
		let isInconclusive = false;
		let result;
		for (const condition of flagConditions) try {
			const conditionAggregation = void 0 !== condition.aggregation_group_type_index ? condition.aggregation_group_type_index : flagAggregation;
			let effectiveProperties = properties;
			let effectiveBucketingValue = bucketingValue;
			if (conditionAggregation !== flagAggregation) {
				if (null != conditionAggregation) {
					const groupName = this.groupTypeMapping[String(conditionAggregation)];
					if (!groupName || !(groupName in groups)) {
						this.logMsgIfDebug(() => console.debug(`[FEATURE FLAGS] Skipping group condition for flag '${flag.key}': group type index ${conditionAggregation} not available`));
						continue;
					}
					if (!(groupName in groupProperties)) {
						isInconclusive = true;
						continue;
					}
					effectiveProperties = groupProperties[groupName];
					effectiveBucketingValue = groups[groupName];
				}
			}
			const matchResult = await this.isConditionMatch(flag, effectiveBucketingValue, condition, effectiveProperties, evaluationContext);
			if ("match" === matchResult) {
				const variantOverride = condition.variant;
				const flagVariants = flagFilters.multivariate?.variants || [];
				result = variantOverride && flagVariants.some((variant) => variant.key === variantOverride) ? variantOverride : await this.getMatchingVariant(flag, effectiveBucketingValue) || true;
				break;
			}
			if (earlyExitEnabled && "out_of_rollout_bound" === matchResult) return false;
		} catch (e) {
			if (e instanceof RequiresServerEvaluation) throw e;
			if (e instanceof InconclusiveMatchError) isInconclusive = true;
			else throw e;
		}
		if (void 0 !== result) return result;
		if (isInconclusive) throw new InconclusiveMatchError("Can't determine if feature flag is enabled or not with given properties");
		return false;
	}
	async isConditionMatch(flag, bucketingValue, condition, properties, evaluationContext) {
		const rolloutPercentage = condition.rollout_percentage;
		const warnFunction = (msg) => {
			this.logMsgIfDebug(() => console.warn(msg));
		};
		if ((condition.properties || []).length > 0) {
			for (const prop of condition.properties) {
				const propertyType = prop.type;
				let matches = false;
				if ("cohort" === propertyType) {
					const inCohort = await matchCohort(prop, properties, this.cohorts, this.debugMode, (depProp) => this.evaluateFlagDependency(depProp, properties, evaluationContext));
					matches = "not_in" === prop.operator ? !inCohort : inCohort;
				} else matches = "flag" === propertyType ? await this.evaluateFlagDependency(prop, properties, evaluationContext) : matchProperty(prop, properties, warnFunction);
				if (!matches) return "no_match";
			}
			if (void 0 == rolloutPercentage) return "match";
		}
		if (void 0 != rolloutPercentage && await _hash(flag.key, bucketingValue) > rolloutPercentage / 100) return "out_of_rollout_bound";
		return "match";
	}
	async getMatchingVariant(flag, bucketingValue) {
		const hashValue = await _hash(flag.key, bucketingValue, "variant");
		const matchingVariant = this.variantLookupTable(flag).find((variant) => hashValue >= variant.valueMin && hashValue < variant.valueMax);
		if (matchingVariant) return matchingVariant.key;
	}
	variantLookupTable(flag) {
		const lookupTable = [];
		let valueMin = 0;
		let valueMax = 0;
		((flag.filters || {}).multivariate?.variants || []).forEach((variant) => {
			valueMax = valueMin + variant.rollout_percentage / 100;
			lookupTable.push({
				valueMin,
				valueMax,
				key: variant.key
			});
			valueMin = valueMax;
		});
		return lookupTable;
	}
	updateFlagState(flagData) {
		this.featureFlags = flagData.flags;
		this.featureFlagsByKey = flagData.flags.reduce((acc, curr) => (acc[curr.key] = curr, acc), {});
		this.groupTypeMapping = flagData.groupTypeMapping;
		this.cohorts = flagData.cohorts;
		this.loadedSuccessfullyOnce = true;
		this.onMinimalFlagCalledEvents?.(true === flagData.minimalFlagCalledEvents);
	}
	warnAboutExperienceContinuityFlags(flags) {
		if (this.strictLocalEvaluation) return;
		const experienceContinuityFlags = flags.filter((f) => f.ensure_experience_continuity);
		if (experienceContinuityFlags.length > 0) console.warn(`[PostHog] You are using local evaluation but ${experienceContinuityFlags.length} flag(s) have experience continuity enabled: ${experienceContinuityFlags.map((f) => f.key).join(", ")}. Experience continuity is incompatible with local evaluation and will cause a server request on every flag evaluation, negating local evaluation cost savings. To avoid server requests and unexpected costs, either disable experience continuity on these flags in PostHog, use strictLocalEvaluation: true in client init, or pass onlyEvaluateLocally: true per flag call (flags that cannot be evaluated locally will return undefined).`);
	}
	async loadFromCache(debugMessage) {
		if (!this.cacheProvider) return false;
		try {
			const cached = await this.cacheProvider.getFlagDefinitions();
			if (cached) {
				this.updateFlagState(cached);
				this.logMsgIfDebug(() => console.debug(`[FEATURE FLAGS] ${debugMessage} (${cached.flags.length} flags)`));
				this.onLoad?.(this.featureFlags.length);
				this.warnAboutExperienceContinuityFlags(cached.flags);
				return true;
			}
			return false;
		} catch (err) {
			this.onError?.(/* @__PURE__ */ new Error(`Failed to load from cache: ${err}`));
			return false;
		}
	}
	async loadFeatureFlags(forceReload = false) {
		if (this.loadedSuccessfullyOnce && !forceReload) return;
		if (!forceReload && this.nextFetchAllowedAt && Date.now() < this.nextFetchAllowedAt) return void this.logMsgIfDebug(() => console.debug("[FEATURE FLAGS] Skipping fetch, in backoff period"));
		if (!this.loadingPromise) this.loadingPromise = this._loadFeatureFlags().catch((err) => this.logMsgIfDebug(() => console.debug(`[FEATURE FLAGS] Failed to load feature flags: ${err}`))).finally(() => {
			this.loadingPromise = void 0;
		});
		return this.loadingPromise;
	}
	isLocalEvaluationReady() {
		return (this.loadedSuccessfullyOnce ?? false) && (this.featureFlags?.length ?? 0) > 0;
	}
	getFlagDefinitionsLoadedAt() {
		return this.flagDefinitionsLoadedAt;
	}
	getPollingInterval() {
		if (!this.shouldBeginExponentialBackoff) return this.pollingInterval;
		return Math.min(SIXTY_SECONDS, this.pollingInterval * 2 ** this.backOffCount);
	}
	beginBackoff() {
		this.shouldBeginExponentialBackoff = true;
		this.backOffCount += 1;
		this.nextFetchAllowedAt = Date.now() + this.getPollingInterval();
	}
	clearBackoff() {
		this.shouldBeginExponentialBackoff = false;
		this.backOffCount = 0;
		this.nextFetchAllowedAt = void 0;
	}
	async _loadFeatureFlags() {
		if (this.poller) {
			clearTimeout(this.poller);
			this.poller = void 0;
		}
		try {
			let shouldFetch = true;
			if (this.cacheProvider) try {
				shouldFetch = await this.cacheProvider.shouldFetchFlagDefinitions();
			} catch (err) {
				this.onError?.(/* @__PURE__ */ new Error(`Error in shouldFetchFlagDefinitions: ${err}`));
			}
			if (!shouldFetch) {
				if (await this.loadFromCache("Loaded flags from cache (skipped fetch)")) return;
				if (this.loadedSuccessfullyOnce) return;
			}
			const res = await this._requestFeatureFlagDefinitions();
			if (!res) return;
			switch (res.status) {
				case 304:
					this.logMsgIfDebug(() => console.debug("[FEATURE FLAGS] Flags not modified (304), using cached data"));
					this.flagsEtag = res.headers?.get("ETag") ?? this.flagsEtag;
					this.loadedSuccessfullyOnce = true;
					this.clearBackoff();
					return;
				case 401:
					this.beginBackoff();
					throw new ClientError(`Your project key or secret key is invalid. Setting next polling interval to ${this.getPollingInterval()}ms. More information: https://posthog.com/docs/api#rate-limiting`);
				case 402:
					console.warn("[FEATURE FLAGS] Feature flags quota limit exceeded - unsetting all local flags. Learn more about billing limits at https://posthog.com/docs/billing/limits-alerts");
					this.featureFlags = [];
					this.featureFlagsByKey = {};
					this.groupTypeMapping = {};
					this.cohorts = {};
					this.onMinimalFlagCalledEvents?.(false);
					return;
				case 403:
					this.beginBackoff();
					throw new ClientError(`Your secret key does not have permission to fetch feature flag definitions for local evaluation. Setting next polling interval to ${this.getPollingInterval()}ms. Are you sure you're using the correct secret and Project API key pair? More information: https://posthog.com/docs/api/overview`);
				case 429:
					this.beginBackoff();
					throw new ClientError(`You are being rate limited. Setting next polling interval to ${this.getPollingInterval()}ms. More information: https://posthog.com/docs/api#rate-limiting`);
				case 200: {
					const responseJson = await res.json() ?? {};
					if (!("flags" in responseJson)) return void this.onError?.(/* @__PURE__ */ new Error(`Invalid response when getting feature flags: ${JSON.stringify(responseJson)}`));
					this.flagsEtag = res.headers?.get("ETag") ?? void 0;
					const flagData = {
						flags: responseJson.flags ?? [],
						groupTypeMapping: responseJson.group_type_mapping || {},
						cohorts: responseJson.cohorts || {},
						minimalFlagCalledEvents: true === responseJson.minimal_flag_called_events
					};
					this.updateFlagState(flagData);
					this.flagDefinitionsLoadedAt = Date.now();
					this.clearBackoff();
					if (this.cacheProvider && shouldFetch) try {
						await this.cacheProvider.onFlagDefinitionsReceived(flagData);
					} catch (err) {
						this.onError?.(/* @__PURE__ */ new Error(`Failed to store in cache: ${err}`));
					}
					this.onLoad?.(this.featureFlags.length);
					this.warnAboutExperienceContinuityFlags(flagData.flags);
					break;
				}
				default: return;
			}
		} catch (err) {
			if (err instanceof ClientError) this.onError?.(err);
		} finally {
			if (!this.pollerStopped) this.poller = setTimeout(() => this.loadFeatureFlags(true), this.getPollingInterval());
		}
	}
	getPersonalApiKeyRequestOptions(method = "GET", etag) {
		const headers = {
			...this.customHeaders,
			"Content-Type": "application/json",
			Authorization: `Bearer ${this.personalApiKey}`
		};
		if (etag) headers["If-None-Match"] = etag;
		return {
			method,
			headers
		};
	}
	async _requestFeatureFlagDefinitions() {
		const url = `${this.host}/flags/definitions?token=${this.projectApiKey}&send_cohorts`;
		const options = this.getPersonalApiKeyRequestOptions("GET", this.flagsEtag);
		let abortTimeout = null;
		if (this.timeout && "number" == typeof this.timeout) {
			const controller = new AbortController();
			abortTimeout = safeSetTimeout(() => {
				controller.abort();
			}, this.timeout);
			options.signal = controller.signal;
		}
		const clearAbortTimeout = () => clearTimeout(abortTimeout);
		try {
			const fetch1 = this.fetch;
			const res = await fetch1(url, options);
			if (200 !== res.status) {
				clearAbortTimeout();
				return res;
			}
			return {
				status: res.status,
				headers: res.headers,
				body: res.body,
				text: async () => {
					try {
						return await res.text();
					} finally {
						clearAbortTimeout();
					}
				},
				json: async () => {
					try {
						return await res.json();
					} finally {
						clearAbortTimeout();
					}
				}
			};
		} catch (err) {
			clearAbortTimeout();
			throw err;
		}
	}
	async stopPoller(timeoutMs = 3e4) {
		this.pollerStopped = true;
		clearTimeout(this.poller);
		this.poller = void 0;
		if (this.cacheProvider) try {
			const shutdownResult = this.cacheProvider.shutdown();
			if (shutdownResult instanceof Promise) await raceWithTimeout(shutdownResult, timeoutMs, () => {
				throw new Error(`Cache shutdown timeout after ${timeoutMs}ms`);
			});
		} catch (err) {
			this.onError?.(/* @__PURE__ */ new Error(`Error during cache shutdown: ${err}`));
		}
	}
};
async function _hash(key, bucketingValue, salt = "") {
	const hashString = await hashSHA1(`${key}.${bucketingValue}${salt}`);
	return parseInt(hashString.slice(0, 15), 16) / LONG_SCALE;
}
function matchProperty(property, propertyValues, warnFunction) {
	const key = property.key;
	const value = property.value;
	const operator = property.operator || "exact";
	if (key in propertyValues) {
		if ("is_not_set" === operator) return false;
	} else {
		if ("is_not_set" === operator) return true;
		throw new InconclusiveMatchError(`Property ${key} not found in propertyValues`);
	}
	const overrideValue = propertyValues[key];
	if (null == overrideValue && !NULL_VALUES_ALLOWED_OPERATORS.includes(operator)) {
		if (warnFunction) warnFunction(`Property ${key} cannot have a value of null/undefined with the ${operator} operator`);
		return false;
	}
	function computeExactMatch(value, overrideValue) {
		if (Array.isArray(value)) return value.map((val) => String(val).toLowerCase()).includes(String(overrideValue).toLowerCase());
		return String(value).toLowerCase() === String(overrideValue).toLowerCase();
	}
	function compare(lhs, rhs, operator) {
		if ("gt" === operator) return lhs > rhs;
		if ("gte" === operator) return lhs >= rhs;
		if ("lt" === operator) return lhs < rhs;
		if ("lte" === operator) return lhs <= rhs;
		throw new Error(`Invalid operator: ${operator}`);
	}
	switch (operator) {
		case "exact": return computeExactMatch(value, overrideValue);
		case "is_not": return !computeExactMatch(value, overrideValue);
		case "is_set": return key in propertyValues;
		case "icontains": return String(overrideValue).toLowerCase().includes(String(value).toLowerCase());
		case "not_icontains": return !String(overrideValue).toLowerCase().includes(String(value).toLowerCase());
		case "starts_with": return String(overrideValue).toLowerCase().startsWith(String(value).toLowerCase());
		case "not_starts_with": return !String(overrideValue).toLowerCase().startsWith(String(value).toLowerCase());
		case "ends_with": return String(overrideValue).toLowerCase().endsWith(String(value).toLowerCase());
		case "not_ends_with": return !String(overrideValue).toLowerCase().endsWith(String(value).toLowerCase());
		case "regex": return isValidRegex(String(value)) && null !== String(overrideValue).match(String(value));
		case "not_regex": return isValidRegex(String(value)) && null === String(overrideValue).match(String(value));
		case "gt":
		case "gte":
		case "lt":
		case "lte": {
			const parsedValue = "number" == typeof value ? value : parseFloat(String(value));
			let parsedOverride;
			parsedOverride = "number" == typeof overrideValue ? overrideValue : null != overrideValue ? parseFloat(String(overrideValue)) : NaN;
			if (Number.isFinite(parsedValue) && Number.isFinite(parsedOverride)) return compare(parsedOverride, parsedValue, operator);
			return compare(String(overrideValue), String(value), operator);
		}
		case "is_date_after":
		case "is_date_before": {
			if ("boolean" == typeof value) throw new InconclusiveMatchError("Date operations cannot be performed on boolean values");
			let parsedDate = relativeDateParseForFeatureFlagMatching(String(value));
			if (null == parsedDate) parsedDate = convertToDateTime(value);
			if (null == parsedDate) throw new InconclusiveMatchError(`Invalid date: ${value}`);
			const overrideDate = convertToDateTime(overrideValue);
			if (["is_date_before"].includes(operator)) return overrideDate < parsedDate;
			return overrideDate > parsedDate;
		}
		case "semver_eq": return 0 === compareSemverTuples(parseSemver(String(overrideValue)), parseSemver(String(value)));
		case "semver_neq": return 0 !== compareSemverTuples(parseSemver(String(overrideValue)), parseSemver(String(value)));
		case "semver_gt": return compareSemverTuples(parseSemver(String(overrideValue)), parseSemver(String(value))) > 0;
		case "semver_gte": return compareSemverTuples(parseSemver(String(overrideValue)), parseSemver(String(value))) >= 0;
		case "semver_lt": return compareSemverTuples(parseSemver(String(overrideValue)), parseSemver(String(value))) < 0;
		case "semver_lte": return compareSemverTuples(parseSemver(String(overrideValue)), parseSemver(String(value))) <= 0;
		case "semver_tilde": {
			const overrideParsed = parseSemver(String(overrideValue));
			const { lower, upper } = computeTildeBounds(String(value));
			return compareSemverTuples(overrideParsed, lower) >= 0 && compareSemverTuples(overrideParsed, upper) < 0;
		}
		case "semver_caret": {
			const overrideParsed = parseSemver(String(overrideValue));
			const { lower, upper } = computeCaretBounds(String(value));
			return compareSemverTuples(overrideParsed, lower) >= 0 && compareSemverTuples(overrideParsed, upper) < 0;
		}
		case "semver_wildcard": {
			const overrideParsed = parseSemver(String(overrideValue));
			const { lower, upper } = computeWildcardBounds(String(value));
			return compareSemverTuples(overrideParsed, lower) >= 0 && compareSemverTuples(overrideParsed, upper) < 0;
		}
		default: throw new InconclusiveMatchError(`Unknown operator: ${operator}`);
	}
}
function checkCohortExists(cohortId, cohortProperties) {
	if (!(cohortId in cohortProperties)) throw new RequiresServerEvaluation(`cohort ${cohortId} not found in local cohorts - likely a static cohort that requires server evaluation`);
}
async function matchCohort(property, propertyValues, cohortProperties, debugMode = false, flagDependencyEvaluator) {
	const cohortId = String(property.value);
	checkCohortExists(cohortId, cohortProperties);
	const propertyGroup = cohortProperties[cohortId];
	return matchPropertyGroup(propertyGroup, propertyValues, cohortProperties, debugMode, flagDependencyEvaluator);
}
async function matchPropertyGroup(propertyGroup, propertyValues, cohortProperties, debugMode = false, flagDependencyEvaluator) {
	if (!propertyGroup) return true;
	const propertyGroupType = propertyGroup.type;
	const properties = propertyGroup.values;
	if (!properties || 0 === properties.length) return true;
	let errorMatchingLocally = false;
	if ("values" in properties[0]) {
		for (const prop of properties) try {
			const matches = await matchPropertyGroup(prop, propertyValues, cohortProperties, debugMode, flagDependencyEvaluator);
			if ("AND" === propertyGroupType) {
				if (!matches) return false;
			} else if (matches) return true;
		} catch (err) {
			if (err instanceof RequiresServerEvaluation) throw err;
			if (err instanceof InconclusiveMatchError) {
				if (debugMode) console.debug(`Failed to compute property ${prop} locally: ${err}`);
				errorMatchingLocally = true;
			} else throw err;
		}
		if (errorMatchingLocally) throw new InconclusiveMatchError("Can't match cohort without a given cohort property value");
		return "AND" === propertyGroupType;
	}
	for (const prop of properties) try {
		let matches;
		if ("cohort" === prop.type) matches = await matchCohort(prop, propertyValues, cohortProperties, debugMode, flagDependencyEvaluator);
		else if ("flag" === prop.type) {
			if (!flagDependencyEvaluator) throw new InconclusiveMatchError(`Flag dependency '${prop.key || "unknown"}' cannot be evaluated without a flag dependency evaluator`);
			matches = await flagDependencyEvaluator(prop);
		} else matches = matchProperty(prop, propertyValues);
		const negation = prop.negation || false;
		if ("AND" === propertyGroupType) {
			if (!matches && !negation) return false;
			if (matches && negation) return false;
		} else {
			if (matches && !negation) return true;
			if (!matches && negation) return true;
		}
	} catch (err) {
		if (err instanceof RequiresServerEvaluation) throw err;
		if (err instanceof InconclusiveMatchError) {
			if (debugMode) console.debug(`Failed to compute property ${prop} locally: ${err}`);
			errorMatchingLocally = true;
		} else throw err;
	}
	if (errorMatchingLocally) throw new InconclusiveMatchError("can't match cohort without a given cohort property value");
	return "AND" === propertyGroupType;
}
function isValidRegex(regex) {
	try {
		new RegExp(regex);
		return true;
	} catch (err) {
		return false;
	}
}
function parseSemverNumericIdentifier(part, raw) {
	if (!/^\d+$/.test(part)) throw new InconclusiveMatchError(`Invalid semver: ${raw}`);
	if (part.length > 1 && "0" === part[0]) throw new InconclusiveMatchError(`Invalid semver: ${raw}`);
	return parseInt(part, 10);
}
function parseSemver(value) {
	const baseVersion = String(value).trim().replace(/^[vV]/, "").split("-")[0].split("+")[0];
	if (!baseVersion || baseVersion.startsWith(".")) throw new InconclusiveMatchError(`Invalid semver: ${value}`);
	const parts = baseVersion.split(".");
	const parsePart = (part) => {
		if (void 0 === part || "" === part) return 0;
		return parseSemverNumericIdentifier(part, value);
	};
	return [
		parsePart(parts[0]),
		parsePart(parts[1]),
		parsePart(parts[2])
	];
}
function compareSemverTuples(a, b) {
	for (let i = 0; i < 3; i++) {
		if (a[i] < b[i]) return -1;
		if (a[i] > b[i]) return 1;
	}
	return 0;
}
function computeTildeBounds(value) {
	const parsed = parseSemver(value);
	return {
		lower: [
			parsed[0],
			parsed[1],
			parsed[2]
		],
		upper: [
			parsed[0],
			parsed[1] + 1,
			0
		]
	};
}
function computeCaretBounds(value) {
	const [major, minor, patch] = parseSemver(value);
	const lower = [
		major,
		minor,
		patch
	];
	let upper;
	upper = major > 0 ? [
		major + 1,
		0,
		0
	] : minor > 0 ? [
		0,
		minor + 1,
		0
	] : [
		0,
		0,
		patch + 1
	];
	return {
		lower,
		upper
	};
}
function computeWildcardBounds(value) {
	const cleanedText = String(value).trim().replace(/^[vV]/, "").replace(/\.\*$/, "").replace(/\*$/, "");
	if (!cleanedText) throw new InconclusiveMatchError(`Invalid wildcard semver: ${value}`);
	const parts = cleanedText.split(".");
	const parseWildcardPart = (part) => {
		try {
			return parseSemverNumericIdentifier(part, value);
		} catch {
			throw new InconclusiveMatchError(`Invalid wildcard semver: ${value}`);
		}
	};
	const major = parseWildcardPart(parts[0]);
	let lower;
	let upper;
	if (1 === parts.length) {
		lower = [
			major,
			0,
			0
		];
		upper = [
			major + 1,
			0,
			0
		];
	} else {
		const minor = parseWildcardPart(parts[1]);
		lower = [
			major,
			minor,
			0
		];
		upper = [
			major,
			minor + 1,
			0
		];
	}
	return {
		lower,
		upper
	};
}
function convertToDateTime(value) {
	if (value instanceof Date) return value;
	if ("string" == typeof value || "number" == typeof value) {
		const date = new Date(value);
		if (!isNaN(date.valueOf())) return date;
		throw new InconclusiveMatchError(`${value} is in an invalid date format`);
	}
	throw new InconclusiveMatchError(`The date provided ${value} must be a string, number, or date object`);
}
function relativeDateParseForFeatureFlagMatching(value) {
	const match = value.match(/^-?(?<number>[0-9]+)(?<interval>[a-z])$/);
	const parsedDt = new Date((/* @__PURE__ */ new Date()).toISOString());
	if (!match) return null;
	{
		if (!match.groups) return null;
		const number = parseInt(match.groups["number"]);
		if (number >= 1e4) return null;
		const interval = match.groups["interval"];
		if ("h" == interval) parsedDt.setUTCHours(parsedDt.getUTCHours() - number);
		else if ("d" == interval) parsedDt.setUTCDate(parsedDt.getUTCDate() - number);
		else if ("w" == interval) parsedDt.setUTCDate(parsedDt.getUTCDate() - 7 * number);
		else if ("m" == interval) parsedDt.setUTCMonth(parsedDt.getUTCMonth() - number);
		else {
			if ("y" != interval) return null;
			parsedDt.setUTCFullYear(parsedDt.getUTCFullYear() - number);
		}
		return parsedDt;
	}
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/error-tracking/autocapture.mjs
const UNHANDLED_REJECTION_OPTION_NAMES = ["--unhandled-rejections", "--unhandled_rejections"];
const UNHANDLED_REJECTION_MODES = /* @__PURE__ */ new Set([
	"throw",
	"strict",
	"warn",
	"warn-with-error-code",
	"none"
]);
const STARTUP_EXEC_ARGV = [...globalThis.process?.execArgv ?? []];
const STARTUP_NODE_OPTIONS = globalThis.process?.env?.NODE_OPTIONS;
function splitNodeOptions(nodeOptions) {
	const args = [];
	let current = "";
	let isInString = false;
	for (let index = 0; index < nodeOptions.length; index++) {
		const character = nodeOptions[index];
		if ("\\" === character && isInString && index + 1 < nodeOptions.length) current += nodeOptions[++index];
		else if (" " !== character || isInString) if ("\"" === character) isInString = !isInString;
		else current += character;
		else if (current) {
			args.push(current);
			current = "";
		}
	}
	if (current) args.push(current);
	return args;
}
function findUnhandledRejectionMode(args) {
	let mode;
	for (let index = 0; index < args.length; index++) {
		const argument = args[index];
		const optionName = UNHANDLED_REJECTION_OPTION_NAMES.find((name) => argument === name || argument.startsWith(`${name}=`));
		if (!optionName) continue;
		const value = argument === optionName ? args[++index] : argument.slice(optionName.length + 1);
		if (UNHANDLED_REJECTION_MODES.has(value)) mode = value;
	}
	return mode;
}
function getUnhandledRejectionMode(execArgv = STARTUP_EXEC_ARGV, nodeOptions = STARTUP_NODE_OPTIONS) {
	return findUnhandledRejectionMode(execArgv) ?? findUnhandledRejectionMode(splitNodeOptions(nodeOptions ?? "")) ?? "throw";
}
const STARTUP_UNHANDLED_REJECTION_MODE = getUnhandledRejectionMode();
function captureUncaughtException(captureFn, error, origin) {
	captureFn(error, { mechanism: {
		type: "unhandledRejection" === origin ? "onunhandledrejection" : "onuncaughtexception",
		handled: false
	} });
}
function makeUncaughtExceptionHandler(captureFn, onFatalFn) {
	let calledFatalError = false;
	return Object.assign((error, origin) => {
		const userProvidedListenersCount = global.process.listeners("uncaughtException").filter((listener) => "domainUncaughtExceptionClear" !== listener.name && true !== listener._posthogErrorHandler).length;
		captureUncaughtException(captureFn, error, origin);
		if (!calledFatalError && 0 === userProvidedListenersCount) {
			calledFatalError = true;
			onFatalFn(error);
		}
	}, { _posthogErrorHandler: true });
}
function addUncaughtExceptionListener(captureFn, onFatalFn, mode = STARTUP_UNHANDLED_REJECTION_MODE) {
	const process = globalThis.process;
	if (!process) return;
	if ("strict" === mode) return void process.on("uncaughtExceptionMonitor", (error, origin) => captureUncaughtException(captureFn, error, origin));
	process.on("uncaughtException", makeUncaughtExceptionHandler(captureFn, onFatalFn));
}
function addUnhandledRejectionListener(captureFn, mode = STARTUP_UNHANDLED_REJECTION_MODE) {
	const process = globalThis.process;
	if (!process || "throw" === mode || "strict" === mode || "warn-with-error-code" === mode) return;
	process.on("unhandledRejection", (reason) => {
		captureFn(reason, { mechanism: {
			type: "onunhandledrejection",
			handled: false
		} });
	});
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/error-tracking/index.mjs
const SHUTDOWN_TIMEOUT = 2e3;
var error_tracking_ErrorTracking = class error_tracking_ErrorTracking {
	constructor(client, options, _logger) {
		this.client = client;
		this._exceptionAutocaptureEnabled = options.enableExceptionAutocapture || false;
		this._logger = _logger;
		this._rateLimiter = new BucketedRateLimiter({
			...resolveExceptionRateLimiterConfig(options),
			refillInterval: 1e4,
			_logger: this._logger
		});
		this.startAutocaptureIfEnabled();
	}
	static isPreviouslyCapturedError(x) {
		return isObject(x) && "__posthog_previously_captured_error" in x && true === x.__posthog_previously_captured_error;
	}
	static async buildEventMessage(builder, error, hint, distinctId, additionalProperties) {
		const properties = { ...additionalProperties };
		const exceptionProperties = builder.buildFromUnknown(error, hint);
		exceptionProperties.$exception_list = await builder.modifyFrames(exceptionProperties.$exception_list);
		const injectedReleaseId = getInjectedReleaseId();
		if (injectedReleaseId) properties.$release_id = injectedReleaseId;
		return {
			event: "$exception",
			distinctId,
			properties: {
				...exceptionProperties,
				...properties
			},
			_originatedFromCaptureException: true
		};
	}
	startAutocaptureIfEnabled() {
		if (this.isEnabled()) {
			addUncaughtExceptionListener(this.onException.bind(this), this.onFatalError.bind(this));
			addUnhandledRejectionListener(this.onException.bind(this));
		}
	}
	onException(exception, hint) {
		this.client.addPendingPromise((async () => {
			if (!error_tracking_ErrorTracking.isPreviouslyCapturedError(exception)) {
				const eventMessage = await error_tracking_ErrorTracking.buildEventMessage(this.client.getErrorPropertiesBuilder(), exception, hint);
				const exceptionType = eventMessage.properties?.$exception_list[0]?.type ?? "Exception";
				if (this._rateLimiter.consumeRateLimit(exceptionType)) return void this._logger.info("Skipping exception capture because of client rate limiting.", { exception: exceptionType });
				return this.client._capturePreparedEvent(eventMessage, false);
			}
		})());
	}
	async onFatalError(exception) {
		console.error(exception);
		await this.client.shutdown(SHUTDOWN_TIMEOUT);
		globalThis.process.exit(1);
	}
	isEnabled() {
		return !this.client.isDisabled && this._exceptionAutocaptureEnabled;
	}
	shutdown() {
		this._rateLimiter.stop();
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/storage-memory.mjs
var PostHogMemoryStorage = class {
	getProperty(key) {
		return this._memoryStorage[key];
	}
	setProperty(key, value) {
		this._memoryStorage[key] = null !== value ? value : void 0;
	}
	constructor() {
		this._memoryStorage = {};
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/capture-v1/config.mjs
function isCaptureMode(value) {
	return "v0" === value || "v1" === value;
}
function resolveCaptureMode() {
	const envMode = "undefined" != typeof process ? process.env?.POSTHOG_CAPTURE_MODE : void 0;
	return isCaptureMode(envMode) ? envMode : "v0";
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/capture-v1/routing.mjs
const AI_EVENT_PREFIX = "$ai_";
function isLegacyOnlyEvent(message) {
	return "string" == typeof message.event && message.event.startsWith(AI_EVENT_PREFIX);
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/capture-v1/errors.mjs
var CaptureV1Error = class CaptureV1Error extends Error {
	constructor({ requestId, drops, retryExhausted, cause }) {
		super(CaptureV1Error.buildMessage(requestId, drops, retryExhausted, cause)), this.name = "CaptureV1Error";
		this.requestId = requestId;
		this.drops = drops;
		this.retryExhausted = retryExhausted;
		this.cause = cause;
	}
	static buildMessage(requestId, drops, retryExhausted, cause) {
		let message = `Capture V1 batch ${requestId} did not fully deliver: ${drops.length} dropped, ${retryExhausted.length} undelivered`;
		if (cause instanceof Error) message += ` (${cause.message})`;
		return message;
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/capture-v1/transform.mjs
function coerceBool(value) {
	if ("boolean" == typeof value) return value;
	if ("number" == typeof value) return 0 !== value;
	if ("string" == typeof value) {
		const normalized = value.trim().toLowerCase();
		if ("true" === normalized || "1" === normalized) return true;
		if ("false" === normalized || "0" === normalized) return false;
	}
}
function coerceString(value) {
	return "string" == typeof value ? value : void 0;
}
const OPTION_SENTINELS = [
	{
		property: "$cookieless_mode",
		optionKey: "cookieless_mode",
		coerce: coerceBool
	},
	{
		property: "$ignore_sent_at",
		optionKey: "disable_skew_correction",
		coerce: coerceBool
	},
	{
		property: "$process_person_profile",
		optionKey: "process_person_profile",
		coerce: coerceBool
	},
	{
		property: "$product_tour_id",
		optionKey: "product_tour_id",
		coerce: coerceString
	}
];
const TOPLEVEL_SENTINELS = [{
	property: "$session_id",
	field: "session_id"
}, {
	property: "$window_id",
	field: "window_id"
}];
function isRecord(value) {
	return "object" == typeof value && null !== value && !Array.isArray(value);
}
function toRfc3339(timestamp) {
	if ("string" == typeof timestamp) {
		const asDate = new Date(timestamp);
		return Number.isNaN(asDate.getTime()) ? (/* @__PURE__ */ new Date()).toISOString() : timestamp;
	}
	if (timestamp instanceof Date) return Number.isNaN(timestamp.getTime()) ? (/* @__PURE__ */ new Date()).toISOString() : timestamp.toISOString();
	const asDate = null == timestamp ? /* @__PURE__ */ new Date() : new Date(timestamp);
	return Number.isNaN(asDate.getTime()) ? (/* @__PURE__ */ new Date()).toISOString() : asDate.toISOString();
}
function relocateInto(properties, key, value) {
	if (void 0 !== value && !(key in properties)) properties[key] = value;
}
function buildV1Event(message) {
	const properties = { ...isRecord(message.properties) ? message.properties : {} };
	const options = {};
	for (const { property, optionKey, coerce } of OPTION_SENTINELS) if (property in properties) {
		const coerced = coerce(properties[property]);
		if (void 0 !== coerced) options[optionKey] = coerced;
		delete properties[property];
	}
	const topLevel = {};
	for (const { property, field } of TOPLEVEL_SENTINELS) if (property in properties) {
		const value = properties[property];
		if ("string" == typeof value) topLevel[field] = value;
		delete properties[property];
	}
	delete properties.$lib;
	delete properties.$lib_version;
	relocateInto(properties, "$set", message.$set);
	relocateInto(properties, "$set_once", message.$set_once);
	return {
		event: String(message.event ?? ""),
		uuid: String(message.uuid ?? ""),
		distinct_id: String(message.distinct_id ?? ""),
		timestamp: toRfc3339(message.timestamp),
		...topLevel,
		options,
		properties
	};
}
function buildV1Batch(messages, { createdAt, historicalMigration }) {
	const batch = {
		created_at: createdAt,
		batch: messages.map(buildV1Event)
	};
	if (historicalMigration) batch.historical_migration = true;
	return batch;
}
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/capture-v1/sender.mjs
const V1_ANALYTICS_PATH = "/i/v1/analytics/events";
const DEFAULT_MAX_BACKOFF_MS = 3e4;
const RETRYABLE_STATUSES = /* @__PURE__ */ new Set([
	408,
	500,
	502,
	503,
	504
]);
var V1CaptureSender = class {
	constructor(config, hooks) {
		this.config = config;
		this.maxBackoffMs = config.maxBackoffMs ?? DEFAULT_MAX_BACKOFF_MS;
		this.fetchFn = hooks.fetch;
		this.onError = hooks.onError;
		this.now = hooks.now ?? Date.now;
		this.sleep = hooks.sleep ?? ((ms) => new Promise((resolve) => safeSetTimeout(resolve, ms)));
		this.generateRequestId = hooks.generateRequestId ?? uuidv7;
		this.compress = hooks.compress ?? gzipCompress;
	}
	async sendV1Batch(messages) {
		if (0 === messages.length) return;
		const requestId = this.generateRequestId();
		const createdAt = new Date(this.now()).toISOString();
		const { batch } = buildV1Batch(messages, {
			createdAt,
			historicalMigration: this.config.historicalMigration
		});
		const url = `${this.config.host}${V1_ANALYTICS_PATH}`;
		const drops = [];
		let pending = batch;
		const maxAttempts = Math.max(1, this.config.maxAttempts);
		for (let attempt = 1; attempt <= maxAttempts; attempt++) {
			const isLastAttempt = attempt === maxAttempts;
			const payload = safeJsonStringify({
				created_at: createdAt,
				...this.config.historicalMigration ? { historical_migration: true } : {},
				batch: pending
			});
			let response;
			try {
				response = await this.sendOnce(url, payload, attempt, requestId);
			} catch (transportError) {
				if (isLastAttempt) return this.surfaceBatchFailure(requestId, drops, pending, transportError);
				await this.sleep(this.backoffDelay(attempt));
				continue;
			}
			const { status } = response;
			if (status < 200 || status >= 300) {
				if (!isLastAttempt && RETRYABLE_STATUSES.has(status)) {
					const retryAfterMs = this.parseRetryAfter(response);
					await this.cancelBody(response);
					await this.sleep(this.backoffDelay(attempt, retryAfterMs));
					continue;
				}
				const httpError = await this.buildHttpError(response, status);
				return this.surfaceBatchFailure(requestId, drops, pending, httpError);
			}
			let parsed;
			try {
				parsed = await this.parseResponse(response);
			} catch {
				return this.surfaceBatchFailure(requestId, drops, pending, /* @__PURE__ */ new Error(`Capture V1 returned an unparseable ${status} response body`));
			}
			const retryable = this.classify(pending, parsed, drops);
			if (0 === retryable.length) return this.surfacePartialDrops(requestId, drops);
			if (isLastAttempt) return void this.onError(new CaptureV1Error({
				requestId,
				drops,
				retryExhausted: retryable.map((event) => event.uuid)
			}));
			pending = retryable;
			const retryAfterMs = this.parseRetryAfter(response);
			await this.sleep(this.backoffDelay(attempt, retryAfterMs));
		}
	}
	async sendOnce(url, payload, attempt, requestId) {
		const headers = this.buildHeaders(attempt, requestId);
		let body = payload;
		if (this.config.compressionEnabled) {
			const compressed = await this.compress(payload, this.config.isDebug);
			if (null !== compressed) {
				body = compressed;
				headers["Content-Encoding"] = "gzip";
			}
		}
		const controller = new AbortController();
		const timer = safeSetTimeout(() => controller.abort(), this.config.requestTimeoutMs);
		try {
			return await this.fetchFn(url, {
				method: "POST",
				headers,
				body,
				signal: controller.signal
			});
		} finally {
			clearTimeout(timer);
		}
	}
	buildHeaders(attempt, requestId) {
		const sdkInfo = `${this.config.libraryId}/${this.config.libraryVersion}`;
		const headers = {
			"Content-Type": "application/json",
			Authorization: `Bearer ${this.config.apiKey}`,
			"PostHog-Sdk-Info": sdkInfo,
			"PostHog-Attempt": String(attempt),
			"PostHog-Request-Id": requestId,
			"PostHog-Request-Timestamp": new Date(this.now()).toISOString()
		};
		if (this.config.userAgent) headers["User-Agent"] = this.config.userAgent;
		return headers;
	}
	classify(pending, parsed, drops) {
		const results = parsed.results ?? {};
		const retryable = [];
		for (const event of pending) {
			const result = results[event.uuid];
			if (result) {
				if ("drop" === result.result) drops.push({
					uuid: event.uuid,
					details: result.details ?? void 0
				});
				else if ("retry" === result.result) retryable.push(event);
			}
		}
		return retryable;
	}
	backoffDelay(attempt, retryAfterMs) {
		const exponential = Math.min(this.config.initialRetryDelayMs * 2 ** (attempt - 1), this.maxBackoffMs);
		if (void 0 === retryAfterMs) return exponential;
		return Math.max(exponential, Math.min(retryAfterMs, this.maxBackoffMs));
	}
	parseRetryAfter(response) {
		const raw = response.headers?.get("Retry-After");
		if (!raw) return;
		const trimmed = raw.trim();
		if (/^\d+$/.test(trimmed)) {
			const seconds = parseInt(trimmed, 10);
			return Number.isFinite(seconds) && seconds > 0 ? 1e3 * seconds : void 0;
		}
		const dateMs = Date.parse(trimmed);
		if (Number.isNaN(dateMs)) return;
		const delta = dateMs - this.now();
		return delta > 0 ? delta : void 0;
	}
	async parseResponse(response) {
		const text = await response.text();
		const parsed = JSON.parse(text);
		if ("object" != typeof parsed || null === parsed || Array.isArray(parsed)) throw new Error("unexpected response shape");
		const results = parsed.results;
		if (void 0 !== results && ("object" != typeof results || null === results || Array.isArray(results))) throw new Error("unexpected results shape");
		return { results: results ?? {} };
	}
	async buildHttpError(response, status) {
		let bodyText = "";
		try {
			bodyText = (await response.text()).slice(0, 512);
		} catch {}
		const suffix = bodyText ? `: ${bodyText}` : "";
		return /* @__PURE__ */ new Error(`Capture V1 request failed with HTTP ${status}${suffix}`);
	}
	surfaceBatchFailure(requestId, drops, pending, cause) {
		this.onError(new CaptureV1Error({
			requestId,
			drops,
			retryExhausted: pending.map((event) => event.uuid),
			cause
		}));
	}
	surfacePartialDrops(requestId, drops) {
		if (drops.length > 0) this.onError(new CaptureV1Error({
			requestId,
			drops,
			retryExhausted: []
		}));
	}
	async cancelBody(response) {
		await response.body?.cancel()?.catch(() => {});
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/client.mjs
const MINIMUM_POLLING_INTERVAL = 100;
const THIRTY_SECONDS = 3e4;
const MAX_CACHE_SIZE = 5e4;
const WAITUNTIL_DEBOUNCE_MS = 50;
const WAITUNTIL_MAX_WAIT_MS = 500;
const DEFAULT_NODE_HOST = "https://us.i.posthog.com";
const _emittedDeprecations = /* @__PURE__ */ new Set();
function emitDeprecationWarningOnce(id, message) {
	if (_emittedDeprecations.has(id)) return;
	_emittedDeprecations.add(id);
	console.warn(`[PostHog] ${message}`);
}
function normalizeApiKey(value) {
	return "string" == typeof value ? value.trim() : "";
}
function normalizePersonalApiKey(value) {
	return ("string" == typeof value ? value.trim() : "") || void 0;
}
function normalizeHost(value) {
	return ("string" == typeof value ? value.trim() : "") || DEFAULT_NODE_HOST;
}
function normalizeUnsetPersonProperties(value) {
	return (Array.isArray(value) ? value : [value]).filter((propertyName) => "string" == typeof propertyName && propertyName.trim().length > 0);
}
function buildFlagEventProperties(flagValues) {
	if (!flagValues) return {};
	const additionalProperties = {};
	for (const [feature, variant] of Object.entries(flagValues)) additionalProperties[`$feature/${feature}`] = variant;
	const activeFlags = Object.keys(flagValues).filter((flag) => false !== flagValues[flag]).sort();
	if (activeFlags.length > 0) additionalProperties["$active_feature_flags"] = activeFlags;
	return additionalProperties;
}
var PostHogBackendClient = class extends PostHogCoreStateless {
	constructor(apiKey, options = {}) {
		const normalizedApiKey = normalizeApiKey(apiKey);
		const normalizedOptions = {
			...options,
			maxQueueSize: options.maxQueueSize ?? 1e4,
			flushInterval: options.flushInterval ?? 5e3,
			host: normalizeHost(options.host),
			personalApiKey: normalizePersonalApiKey(options.secretKey ?? options.personalApiKey)
		};
		super(normalizedApiKey, normalizedOptions), this._memoryStorage = new PostHogMemoryStorage(), this._minimalFlagCalledEvents = false;
		this.options = normalizedOptions;
		this.captureMode = resolveCaptureMode();
		this.context = this.initializeContext();
		this.options.featureFlagsPollingInterval = "number" == typeof normalizedOptions.featureFlagsPollingInterval ? Math.max(normalizedOptions.featureFlagsPollingInterval, MINIMUM_POLLING_INTERVAL) : THIRTY_SECONDS;
		if ("number" == typeof normalizedOptions.waitUntilDebounceMs) this.options.waitUntilDebounceMs = Math.max(normalizedOptions.waitUntilDebounceMs, 0);
		if ("number" == typeof normalizedOptions.waitUntilMaxWaitMs) this.options.waitUntilMaxWaitMs = Math.max(normalizedOptions.waitUntilMaxWaitMs, 0);
		if (!this.disabled && normalizedOptions.personalApiKey) {
			if (normalizedOptions.personalApiKey.includes("phc_")) throw new Error("Your Personal API key is invalid. These keys are prefixed with \"phx_\" and can be created in PostHog project settings.");
			if (false !== normalizedOptions.enableLocalEvaluation) this.featureFlagsPoller = new FeatureFlagsPoller({
				pollingInterval: this.options.featureFlagsPollingInterval,
				personalApiKey: normalizedOptions.personalApiKey,
				projectApiKey: normalizedApiKey,
				timeout: normalizedOptions.requestTimeout ?? 1e4,
				host: this.host,
				fetch: normalizedOptions.fetch,
				onError: (err) => {
					this._events.emit("error", err);
				},
				onLoad: (count) => {
					this._events.emit("localEvaluationFlagsLoaded", count);
				},
				onMinimalFlagCalledEvents: (enabled) => {
					this._minimalFlagCalledEvents = enabled;
				},
				customHeaders: this.getCustomHeaders(),
				cacheProvider: normalizedOptions.flagDefinitionCacheProvider,
				strictLocalEvaluation: normalizedOptions.strictLocalEvaluation
			});
		}
		this.errorTracking = new error_tracking_ErrorTracking(this, normalizedOptions, this._logger);
		this.distinctIdHasSentFlagCalls = {};
		this.maxCacheSize = normalizedOptions.maxCacheSize || MAX_CACHE_SIZE;
	}
	enqueue(type, message, options) {
		super.enqueue(type, message, options);
		this.scheduleDebouncedFlush();
	}
	async flush() {
		const flushPromise = this.flushWithPendingPromises();
		const waitUntil = this.options.waitUntil;
		if (waitUntil && !this._waitUntilCycle) try {
			waitUntil(flushPromise.catch(() => {}));
		} catch {}
		return flushPromise;
	}
	scheduleDebouncedFlush() {
		const waitUntil = this.options.waitUntil;
		if (!waitUntil) return;
		if (this.disabled || this.optedOut) return;
		if (!this._waitUntilCycle) {
			let resolve;
			const promise = new Promise((r) => {
				resolve = r;
			});
			try {
				waitUntil(promise);
			} catch {
				return;
			}
			this._waitUntilCycle = {
				resolve,
				startedAt: Date.now(),
				timer: void 0
			};
		}
		const flushNow = Date.now() - this._waitUntilCycle.startedAt >= (this.options.waitUntilMaxWaitMs ?? WAITUNTIL_MAX_WAIT_MS);
		if (void 0 !== this._waitUntilCycle.timer) clearTimeout(this._waitUntilCycle.timer);
		if (flushNow) return void this.resolveWaitUntilFlush();
		const debounceMs = this.options.waitUntilDebounceMs ?? WAITUNTIL_DEBOUNCE_MS;
		this._waitUntilCycle.timer = safeSetTimeout(() => {
			this.resolveWaitUntilFlush();
		}, debounceMs);
	}
	_consumeWaitUntilCycle() {
		const cycle = this._waitUntilCycle;
		if (cycle) {
			clearTimeout(cycle.timer);
			this._waitUntilCycle = void 0;
		}
		return cycle?.resolve;
	}
	async resolveWaitUntilFlush() {
		const resolve = this._consumeWaitUntilCycle();
		try {
			await this.flushWithPendingPromises();
		} catch {} finally {
			resolve?.();
		}
	}
	getPersistedProperty(key) {
		return this._memoryStorage.getProperty(key);
	}
	setPersistedProperty(key, value) {
		return this._memoryStorage.setProperty(key, value);
	}
	fetch(url, options) {
		return this.options.fetch ? this.options.fetch(url, options) : fetch(url, options);
	}
	getQueueRouteKey(message) {
		return "v1" === this.captureMode && isLegacyOnlyEvent(message) ? "ai" : "analytics";
	}
	persistedQueueKeyForRoute(route) {
		return route === "ai" ? types_PostHogPersistedProperty.AiQueue : types_PostHogPersistedProperty.Queue;
	}
	getActiveQueueRoutes() {
		return "v1" === this.captureMode ? ["analytics", "ai"] : ["analytics"];
	}
	async sendBatch(batchMessages, retryOptions, route = "analytics") {
		if ("v1" !== this.captureMode || route === "ai") return super.sendBatch(batchMessages, retryOptions, route);
		const v1Events = batchMessages.filter((message) => void 0 !== message);
		await this.getV1Sender().sendV1Batch(v1Events);
	}
	getV1Sender() {
		if (!this._v1Sender) this._v1Sender = new V1CaptureSender({
			host: this.host,
			apiKey: this.apiKey,
			libraryId: this.getLibraryId(),
			libraryVersion: this.getLibraryVersion(),
			userAgent: this.getCustomUserAgent() || void 0,
			historicalMigration: this.historicalMigration,
			compressionEnabled: !this.disableCompression,
			requestTimeoutMs: this.requestTimeout,
			maxAttempts: (this.options.fetchRetryCount ?? 3) + 1,
			initialRetryDelayMs: this.options.fetchRetryDelay ?? 3e3,
			isDebug: this.isDebug
		}, {
			fetch: (url, fetchOptions) => this.fetch(url, fetchOptions),
			onError: (error) => this._events.emit("error", error)
		});
		return this._v1Sender;
	}
	getLibraryVersion() {
		return "5.48.0";
	}
	get metrics() {
		if (!this._metrics) this._metrics = new PostHogMetrics(this, resolveMetricsConfig(this.options.metrics), this._logger);
		return this._metrics;
	}
	getCustomUserAgent() {
		return `${this.getLibraryId()}/${this.getLibraryVersion()}`;
	}
	getCommonEventProperties() {
		const commonProperties = super.getCommonEventProperties();
		if (this.options.isServer ?? true) commonProperties.$is_server = true;
		return commonProperties;
	}
	enable() {
		return super.optIn();
	}
	disable() {
		return super.optOut();
	}
	debug(enabled = true) {
		super.debug(enabled);
		this.featureFlagsPoller?.debug(enabled);
	}
	_warnIfInvalidCapture(props, stringArgumentWarning, exceptionCaptureWarning) {
		if ("string" == typeof props) this._logger.warn(stringArgumentWarning);
		if ("$exception" === props.event && !props._originatedFromCaptureException) this._logger.warn(exceptionCaptureWarning);
	}
	_sendPreparedEvent(type, props, immediate, prepareOptions) {
		return this.addPendingPromise(this._prepareEventMessage(props, prepareOptions).then(({ distinctId, event, properties, options }) => {
			const captureOptions = {
				timestamp: options.timestamp,
				disableGeoip: options.disableGeoip,
				uuid: options.uuid
			};
			const message = {
				distinctId,
				event,
				properties: {
					...properties,
					...this.getCommonEventProperties()
				}
			};
			return immediate ? this.sendImmediate(type, message, captureOptions) : this.enqueue(type, message, captureOptions);
		}).catch((err) => {
			if (err) console.error(err);
		}));
	}
	_capturePreparedEvent(props, immediate) {
		return this._sendPreparedEvent("capture", props, immediate);
	}
	capture(props) {
		this._warnIfInvalidCapture(props, "Called capture() with a string as the first argument when an object was expected.", "Using `posthog.capture('$exception')` is unreliable because it does not attach required metadata. Use `posthog.captureException(error)` instead, which attaches required metadata automatically.");
		this._capturePreparedEvent(props, false);
	}
	async captureImmediate(props) {
		this._warnIfInvalidCapture(props, "Called captureImmediate() with a string as the first argument when an object was expected.", "Capturing a `$exception` event via `posthog.captureImmediate('$exception')` is unreliable because it does not attach required metadata. Use `posthog.captureExceptionImmediate(error)` instead, which attaches this metadata by default.");
		return this._capturePreparedEvent(props, true);
	}
	identify({ distinctId, properties = {}, disableGeoip }) {
		const { $set, $set_once, $anon_distinct_id, ...rest } = properties;
		const eventProperties = {
			$set: $set || rest,
			$set_once: $set_once || {},
			$anon_distinct_id: $anon_distinct_id ?? void 0
		};
		this._sendPreparedEvent("identify", {
			distinctId,
			event: "$identify",
			properties: eventProperties,
			disableGeoip
		}, false, { includeContextProperties: false });
	}
	async identifyImmediate({ distinctId, properties = {}, disableGeoip }) {
		const { $set, $set_once, $anon_distinct_id, ...rest } = properties;
		const eventProperties = {
			$set: $set || rest,
			$set_once: $set_once || {},
			$anon_distinct_id: $anon_distinct_id ?? void 0
		};
		await this._sendPreparedEvent("identify", {
			distinctId,
			event: "$identify",
			properties: eventProperties,
			disableGeoip
		}, true, { includeContextProperties: false });
	}
	setPersonProperties({ distinctId, properties = {}, propertiesOnce = {} }) {
		if (0 === Object.keys(properties).length && 0 === Object.keys(propertiesOnce).length) return;
		const eventProperties = {};
		if (Object.keys(properties).length > 0) eventProperties.$set = properties;
		if (Object.keys(propertiesOnce).length > 0) eventProperties.$set_once = propertiesOnce;
		this.capture({
			distinctId,
			event: "$set",
			properties: eventProperties
		});
	}
	unsetPersonProperties({ distinctId, properties }) {
		const propertyNames = normalizeUnsetPersonProperties(properties);
		if (0 === propertyNames.length) return;
		this.capture({
			distinctId,
			event: "$set",
			properties: { $unset: propertyNames }
		});
	}
	alias(data) {
		this._sendPreparedEvent("alias", {
			distinctId: data.distinctId,
			event: "$create_alias",
			properties: {
				distinct_id: data.distinctId,
				alias: data.alias
			},
			disableGeoip: data.disableGeoip
		}, false, { includeContextProperties: false });
	}
	async aliasImmediate(data) {
		await this._sendPreparedEvent("alias", {
			distinctId: data.distinctId,
			event: "$create_alias",
			properties: {
				distinct_id: data.distinctId,
				alias: data.alias
			},
			disableGeoip: data.disableGeoip
		}, true, { includeContextProperties: false });
	}
	isLocalEvaluationReady() {
		return this.featureFlagsPoller?.isLocalEvaluationReady() ?? false;
	}
	async waitForLocalEvaluationReady(timeoutMs = THIRTY_SECONDS) {
		if (this.isLocalEvaluationReady()) return true;
		if (void 0 === this.featureFlagsPoller) return false;
		return new Promise((resolve) => {
			const timeout = setTimeout(() => {
				cleanup();
				resolve(false);
			}, timeoutMs);
			const cleanup = this._events.on("localEvaluationFlagsLoaded", (count) => {
				clearTimeout(timeout);
				cleanup();
				resolve(count > 0);
			});
		});
	}
	_resolveDistinctId(distinctIdOrOptions, options) {
		if ("string" == typeof distinctIdOrOptions) return {
			distinctId: distinctIdOrOptions,
			options
		};
		return {
			distinctId: this.context?.get()?.distinctId,
			options: distinctIdOrOptions
		};
	}
	async _getFeatureFlagResult(key, distinctId, options = {}, matchValue) {
		if (this.disabled) return void this._logger.warn("The client is disabled");
		const sendFeatureFlagEvents = options.sendFeatureFlagEvents ?? true;
		if (void 0 !== this._flagOverrides && key in this._flagOverrides) {
			const overrideValue = this._flagOverrides[key];
			if (void 0 === overrideValue) return;
			const overridePayload = this._payloadOverrides?.[key];
			return {
				key,
				enabled: false !== overrideValue,
				variant: "string" == typeof overrideValue ? overrideValue : void 0,
				payload: overridePayload
			};
		}
		const { groups, disableGeoip } = options;
		let { onlyEvaluateLocally, personProperties, groupProperties } = options;
		const adjustedProperties = this.addLocalPersonAndGroupProperties(distinctId, groups, personProperties, groupProperties);
		personProperties = adjustedProperties.allPersonProperties;
		groupProperties = adjustedProperties.allGroupProperties;
		const evaluationContext = this.createFeatureFlagEvaluationContext(distinctId, groups, this.personPropertiesForLocalEvaluation(distinctId, personProperties), groupProperties);
		if (void 0 == onlyEvaluateLocally) onlyEvaluateLocally = this.options.strictLocalEvaluation ?? false;
		let result;
		let flagWasLocallyEvaluated = false;
		let requestId;
		let evaluatedAt;
		let featureFlagError;
		let flagId;
		let flagVersion;
		let flagReason;
		let flagHasExperiment;
		if (void 0 !== this.featureFlagsPoller) {
			await this.featureFlagsPoller?.loadFeatureFlags();
			const flag = this.featureFlagsPoller?.featureFlagsByKey[key];
			if (flag) try {
				const localResult = await this.featureFlagsPoller?.computeFlagAndPayloadLocally(flag, evaluationContext, { matchValue });
				if (localResult) {
					flagWasLocallyEvaluated = true;
					const value = localResult.value;
					flagId = flag.id;
					flagReason = "Evaluated locally";
					flagHasExperiment = flag.has_experiment;
					result = {
						key,
						enabled: false !== value,
						variant: "string" == typeof value ? value : void 0,
						payload: localResult.payload ?? void 0
					};
				}
			} catch (e) {
				if (e instanceof RequiresServerEvaluation || e instanceof InconclusiveMatchError) this._logger?.info(`${e.name} when computing flag locally: ${key}: ${e.message}`);
				else throw e;
			}
		}
		if (!flagWasLocallyEvaluated && !onlyEvaluateLocally) {
			const flagsResponse = await super.getFeatureFlagDetailsStateless(evaluationContext.distinctId, evaluationContext.groups, personProperties, groupProperties, disableGeoip, [key]);
			if (void 0 === flagsResponse) featureFlagError = FeatureFlagError.UNKNOWN_ERROR;
			else {
				this._minimalFlagCalledEvents = true === flagsResponse.minimalFlagCalledEvents;
				requestId = flagsResponse.requestId;
				evaluatedAt = flagsResponse.evaluatedAt;
				const errors = [];
				if (flagsResponse.errorsWhileComputingFlags) errors.push(FeatureFlagError.ERRORS_WHILE_COMPUTING);
				if (flagsResponse.quotaLimited?.includes("feature_flags")) errors.push(FeatureFlagError.QUOTA_LIMITED);
				const flagDetail = flagsResponse.flags[key];
				if (void 0 === flagDetail) errors.push(FeatureFlagError.FLAG_MISSING);
				else {
					flagId = flagDetail.metadata?.id;
					flagVersion = flagDetail.metadata?.version;
					flagReason = flagDetail.reason?.description ?? flagDetail.reason?.code;
					flagHasExperiment = flagDetail.metadata?.has_experiment;
					let parsedPayload;
					if (flagDetail.metadata?.payload !== void 0) try {
						parsedPayload = JSON.parse(flagDetail.metadata.payload);
					} catch {
						parsedPayload = flagDetail.metadata.payload;
					}
					result = {
						key,
						enabled: flagDetail.enabled,
						variant: flagDetail.variant,
						payload: parsedPayload
					};
				}
				if (errors.length > 0) featureFlagError = errors.join(",");
			}
		}
		if (sendFeatureFlagEvents) {
			const response = void 0 === result ? void 0 : false === result.enabled ? false : result.variant ?? true;
			const properties = {
				$feature_flag: key,
				$feature_flag_response: response,
				$feature_flag_id: flagId,
				$feature_flag_version: flagVersion,
				$feature_flag_reason: flagReason,
				locally_evaluated: flagWasLocallyEvaluated,
				[`$feature/${key}`]: response,
				$feature_flag_request_id: requestId,
				$feature_flag_evaluated_at: flagWasLocallyEvaluated ? Date.now() : evaluatedAt
			};
			if (void 0 !== flagHasExperiment) properties.$feature_flag_has_experiment = flagHasExperiment;
			if (flagWasLocallyEvaluated && this.featureFlagsPoller) {
				const flagDefinitionsLoadedAt = this.featureFlagsPoller.getFlagDefinitionsLoadedAt();
				if (void 0 !== flagDefinitionsLoadedAt) properties.$feature_flag_definitions_loaded_at = flagDefinitionsLoadedAt;
			}
			if (featureFlagError) properties.$feature_flag_error = featureFlagError;
			this._captureFlagCalledEventIfNeeded({
				distinctId,
				key,
				response,
				groups,
				disableGeoip,
				properties
			});
		}
		if (void 0 !== result && void 0 !== this._payloadOverrides && key in this._payloadOverrides) result = {
			...result,
			payload: this._payloadOverrides[key]
		};
		return result;
	}
	async getFeatureFlag(key, distinctId, options) {
		emitDeprecationWarningOnce("getFeatureFlag", "`getFeatureFlag` is deprecated and will be removed in a future major version. Use `posthog.evaluateFlags(distinctId, ...)` and call `flags.getFlag(key)` instead — this consolidates flag evaluation into a single `/flags` request per incoming request.");
		const result = await this._getFeatureFlagResult(key, distinctId, {
			...options,
			sendFeatureFlagEvents: options?.sendFeatureFlagEvents ?? this.options.sendFeatureFlagEvent ?? true
		});
		if (void 0 === result) return;
		if (false === result.enabled) return false;
		return result.variant ?? true;
	}
	async getFeatureFlagPayload(key, distinctId, matchValue, options) {
		emitDeprecationWarningOnce("getFeatureFlagPayload", "`getFeatureFlagPayload` is deprecated and will be removed in a future major version. Use `posthog.evaluateFlags(distinctId, ...)` and call `flags.getFlagPayload(key)` instead — this consolidates flag evaluation into a single `/flags` request per incoming request.");
		if (void 0 !== this._payloadOverrides && key in this._payloadOverrides) return this._payloadOverrides[key];
		const result = await this._getFeatureFlagResult(key, distinctId, {
			...options,
			sendFeatureFlagEvents: false
		}, matchValue);
		if (void 0 === result) return;
		return result.payload ?? null;
	}
	async getFeatureFlagResult(key, distinctIdOrOptions, options) {
		const { distinctId: resolvedDistinctId, options: resolvedOptions } = this._resolveDistinctId(distinctIdOrOptions, options);
		if (!resolvedDistinctId) return void this._logger.warn("[PostHog] distinctId is required — pass it explicitly or use withContext()");
		return this._getFeatureFlagResult(key, resolvedDistinctId, {
			...resolvedOptions,
			sendFeatureFlagEvents: resolvedOptions?.sendFeatureFlagEvents ?? this.options.sendFeatureFlagEvent ?? true
		});
	}
	async getRemoteConfigPayload(flagKey) {
		if (this.disabled) return void this._logger.warn("The client is disabled");
		if (!this.options.personalApiKey) throw new Error("Personal API key is required for remote config payload decryption");
		const response = await this._requestRemoteConfigPayload(flagKey);
		if (!response) return;
		const parsed = await response.json();
		if ("string" == typeof parsed) try {
			return JSON.parse(parsed);
		} catch (e) {}
		return parsed;
	}
	async isFeatureEnabled(key, distinctId, options) {
		emitDeprecationWarningOnce("isFeatureEnabled", "`isFeatureEnabled` is deprecated and will be removed in a future major version. Use `posthog.evaluateFlags(distinctId, ...)` and call `flags.isEnabled(key)` instead — this consolidates flag evaluation into a single `/flags` request per incoming request.");
		const result = await this._getFeatureFlagResult(key, distinctId, {
			...options,
			sendFeatureFlagEvents: options?.sendFeatureFlagEvents ?? this.options.sendFeatureFlagEvent ?? true
		});
		if (void 0 === result) return;
		if (false === result.enabled) return false;
		return !!(result.variant ?? true) || false;
	}
	async getAllFlags(distinctIdOrOptions, options) {
		const { distinctId: resolvedDistinctId, options: resolvedOptions } = this._resolveDistinctId(distinctIdOrOptions, options);
		if (!resolvedDistinctId) {
			this._logger.warn("[PostHog] distinctId is required to get feature flags — pass it explicitly or use withContext()");
			return {};
		}
		return (await this.getAllFlagsAndPayloads(resolvedDistinctId, resolvedOptions)).featureFlags || {};
	}
	async getAllFlagsAndPayloads(distinctIdOrOptions, options) {
		const { distinctId: resolvedDistinctId, options: resolvedOptions } = this._resolveDistinctId(distinctIdOrOptions, options);
		if (!resolvedDistinctId) {
			this._logger.warn("[PostHog] distinctId is required to get feature flags and payloads — pass it explicitly or use withContext()");
			return {
				featureFlags: {},
				featureFlagPayloads: {}
			};
		}
		if (this.disabled) {
			this._logger.warn("The client is disabled");
			return {
				featureFlags: {},
				featureFlagPayloads: {}
			};
		}
		const { groups, disableGeoip, flagKeys } = resolvedOptions || {};
		let { onlyEvaluateLocally, personProperties, groupProperties } = resolvedOptions || {};
		const adjustedProperties = this.addLocalPersonAndGroupProperties(resolvedDistinctId, groups, personProperties, groupProperties);
		personProperties = adjustedProperties.allPersonProperties;
		groupProperties = adjustedProperties.allGroupProperties;
		const evaluationContext = this.createFeatureFlagEvaluationContext(resolvedDistinctId, groups, this.personPropertiesForLocalEvaluation(resolvedDistinctId, personProperties), groupProperties);
		if (void 0 == onlyEvaluateLocally) onlyEvaluateLocally = this.options.strictLocalEvaluation ?? false;
		const localEvaluationResult = await this.featureFlagsPoller?.getAllFlagsAndPayloads(evaluationContext, flagKeys);
		let featureFlags = {};
		let featureFlagPayloads = {};
		let fallbackToFlags = true;
		if (localEvaluationResult) {
			featureFlags = localEvaluationResult.response;
			featureFlagPayloads = localEvaluationResult.payloads;
			fallbackToFlags = localEvaluationResult.fallbackToFlags;
		}
		if (fallbackToFlags && !onlyEvaluateLocally) {
			const remoteEvaluationResult = await super.getFeatureFlagsAndPayloadsStateless(evaluationContext.distinctId, evaluationContext.groups, personProperties, groupProperties, disableGeoip, flagKeys);
			featureFlags = {
				...featureFlags,
				...remoteEvaluationResult.flags || {}
			};
			featureFlagPayloads = {
				...featureFlagPayloads,
				...remoteEvaluationResult.payloads || {}
			};
		}
		if (void 0 !== this._flagOverrides) featureFlags = {
			...featureFlags,
			...this._flagOverrides
		};
		if (void 0 !== this._payloadOverrides) featureFlagPayloads = {
			...featureFlagPayloads,
			...this._payloadOverrides
		};
		return {
			featureFlags,
			featureFlagPayloads
		};
	}
	async evaluateFlags(distinctIdOrOptions, options) {
		const { distinctId: resolvedDistinctId, options: resolvedOptions } = this._resolveDistinctId(distinctIdOrOptions, options);
		if (!resolvedDistinctId) {
			this._logger.warn("[PostHog] distinctId is required to evaluate feature flags — pass it explicitly or use withContext()");
			return new FeatureFlagEvaluations({
				host: this._getFeatureFlagEvaluationsHost(),
				distinctId: "",
				flags: {}
			});
		}
		if (this.disabled) {
			this._logger.warn("The client is disabled");
			return new FeatureFlagEvaluations({
				host: this._getFeatureFlagEvaluationsHost(),
				distinctId: resolvedDistinctId,
				flags: {}
			});
		}
		const { groups, disableGeoip, flagKeys } = resolvedOptions || {};
		let { onlyEvaluateLocally, personProperties, groupProperties } = resolvedOptions || {};
		const adjustedProperties = this.addLocalPersonAndGroupProperties(resolvedDistinctId, groups, personProperties, groupProperties);
		personProperties = adjustedProperties.allPersonProperties;
		groupProperties = adjustedProperties.allGroupProperties;
		const evaluationContext = this.createFeatureFlagEvaluationContext(resolvedDistinctId, groups, this.personPropertiesForLocalEvaluation(resolvedDistinctId, personProperties), groupProperties);
		if (void 0 == onlyEvaluateLocally) onlyEvaluateLocally = this.options.strictLocalEvaluation ?? false;
		const records = {};
		let requestId;
		let evaluatedAt;
		let errorsWhileComputing = false;
		let quotaLimited = false;
		const localResult = await this.featureFlagsPoller?.getAllFlagsAndPayloads(evaluationContext, flagKeys);
		const locallyEvaluatedKeys = /* @__PURE__ */ new Set();
		if (localResult) for (const [key, value] of Object.entries(localResult.response)) {
			const flagDef = this.featureFlagsPoller?.featureFlagsByKey[key];
			records[key] = {
				key,
				enabled: false !== value,
				variant: "string" == typeof value ? value : void 0,
				payload: localResult.payloads[key],
				id: flagDef?.id,
				version: void 0,
				reason: "Evaluated locally",
				locallyEvaluated: true,
				hasExperiment: flagDef?.has_experiment
			};
			locallyEvaluatedKeys.add(key);
		}
		if ((localResult ? localResult.fallbackToFlags : true) && !onlyEvaluateLocally) {
			const details = await super.getFeatureFlagDetailsStateless(evaluationContext.distinctId, evaluationContext.groups, personProperties, groupProperties, disableGeoip, flagKeys);
			if (details) {
				this._minimalFlagCalledEvents = true === details.minimalFlagCalledEvents;
				requestId = details.requestId;
				evaluatedAt = details.evaluatedAt;
				errorsWhileComputing = Boolean(details.errorsWhileComputingFlags);
				quotaLimited = Array.isArray(details.quotaLimited) && details.quotaLimited.includes("feature_flags");
				for (const [key, detail] of Object.entries(details.flags)) {
					if (locallyEvaluatedKeys.has(key)) continue;
					let parsedPayload;
					if (detail.metadata?.payload !== void 0) try {
						parsedPayload = JSON.parse(detail.metadata.payload);
					} catch {
						parsedPayload = detail.metadata.payload;
					}
					records[key] = {
						key,
						enabled: detail.enabled,
						variant: detail.variant,
						payload: parsedPayload,
						id: detail.metadata?.id,
						version: detail.metadata?.version,
						reason: detail.reason?.description ?? detail.reason?.code,
						locallyEvaluated: false,
						hasExperiment: detail.metadata?.has_experiment
					};
				}
			}
		}
		if (void 0 !== this._flagOverrides) for (const [key, value] of Object.entries(this._flagOverrides)) {
			if (void 0 === value) {
				delete records[key];
				continue;
			}
			const existing = records[key];
			records[key] = {
				key,
				enabled: false !== value,
				variant: "string" == typeof value ? value : void 0,
				payload: existing?.payload,
				id: existing?.id,
				version: existing?.version,
				reason: existing?.reason,
				locallyEvaluated: existing?.locallyEvaluated ?? false,
				hasExperiment: existing?.hasExperiment
			};
		}
		if (void 0 !== this._payloadOverrides) for (const [key, payload] of Object.entries(this._payloadOverrides)) {
			const existing = records[key];
			if (existing) records[key] = {
				...existing,
				payload
			};
		}
		return new FeatureFlagEvaluations({
			host: this._getFeatureFlagEvaluationsHost(),
			distinctId: resolvedDistinctId,
			groups,
			disableGeoip,
			flags: records,
			requestId,
			evaluatedAt,
			flagDefinitionsLoadedAt: this.featureFlagsPoller?.getFlagDefinitionsLoadedAt(),
			errorsWhileComputing,
			quotaLimited
		});
	}
	_shouldSendMinimalFlagCalledEvent(event, properties) {
		return "$feature_flag_called" === event && this._minimalFlagCalledEvents && false === properties.$feature_flag_has_experiment;
	}
	_captureFlagCalledEventIfNeeded(params) {
		const { distinctId, key, response, groups, disableGeoip, properties } = params;
		const featureFlagReportedKey = `${key}_${response}${groups && Object.keys(groups).length > 0 ? `_${JSON.stringify(Object.entries(groups).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0))}` : ""}`;
		if (distinctId in this.distinctIdHasSentFlagCalls && this.distinctIdHasSentFlagCalls[distinctId].has(featureFlagReportedKey)) return;
		if (Object.keys(this.distinctIdHasSentFlagCalls).length >= this.maxCacheSize) this.distinctIdHasSentFlagCalls = {};
		if (this.distinctIdHasSentFlagCalls[distinctId] instanceof Set) this.distinctIdHasSentFlagCalls[distinctId].add(featureFlagReportedKey);
		else this.distinctIdHasSentFlagCalls[distinctId] = /* @__PURE__ */ new Set([featureFlagReportedKey]);
		this.capture({
			distinctId,
			event: "$feature_flag_called",
			properties,
			groups,
			disableGeoip
		});
	}
	_getFeatureFlagEvaluationsHost() {
		if (!this._featureFlagEvaluationsHost) this._featureFlagEvaluationsHost = {
			captureFlagCalledEventIfNeeded: (params) => this._captureFlagCalledEventIfNeeded(params),
			logWarning: (message) => {
				if (false !== this.options.featureFlagsLogWarnings) console.warn(`[PostHog] ${message}`);
			}
		};
		return this._featureFlagEvaluationsHost;
	}
	groupIdentify({ groupType, groupKey, properties, distinctId, disableGeoip }) {
		this._sendPreparedEvent("capture", {
			distinctId: distinctId || `$${groupType}_${groupKey}`,
			event: "$groupidentify",
			properties: {
				$group_type: groupType,
				$group_key: groupKey,
				$group_set: properties || {}
			},
			disableGeoip
		}, false, { includeContextProperties: false });
	}
	async groupIdentifyImmediate({ groupType, groupKey, properties, distinctId, disableGeoip }) {
		await this._sendPreparedEvent("capture", {
			distinctId: distinctId || `$${groupType}_${groupKey}`,
			event: "$groupidentify",
			properties: {
				$group_type: groupType,
				$group_key: groupKey,
				$group_set: properties || {}
			},
			disableGeoip
		}, true, { includeContextProperties: false });
	}
	async reloadFeatureFlags() {
		await this.featureFlagsPoller?.loadFeatureFlags(true);
	}
	overrideFeatureFlags(overrides) {
		const flagArrayToRecord = (flags) => Object.fromEntries(flags.map((f) => [f, true]));
		if (false === overrides) {
			this._flagOverrides = void 0;
			this._payloadOverrides = void 0;
			return;
		}
		if (Array.isArray(overrides)) {
			this._flagOverrides = flagArrayToRecord(overrides);
			return;
		}
		if (this._isFeatureFlagOverrideOptions(overrides)) {
			if ("flags" in overrides) {
				if (false === overrides.flags) this._flagOverrides = void 0;
				else if (Array.isArray(overrides.flags)) this._flagOverrides = flagArrayToRecord(overrides.flags);
				else if (void 0 !== overrides.flags) this._flagOverrides = { ...overrides.flags };
			}
			if ("payloads" in overrides) {
				if (false === overrides.payloads) this._payloadOverrides = void 0;
				else if (void 0 !== overrides.payloads) this._payloadOverrides = { ...overrides.payloads };
			}
			return;
		}
		this._flagOverrides = { ...overrides };
	}
	_isFeatureFlagOverrideOptions(overrides) {
		if ("object" != typeof overrides || null === overrides || Array.isArray(overrides)) return false;
		const obj = overrides;
		if ("flags" in obj) {
			const flagsValue = obj["flags"];
			if (false === flagsValue || Array.isArray(flagsValue) || "object" == typeof flagsValue && null !== flagsValue) return true;
		}
		if ("payloads" in obj) {
			const payloadsValue = obj["payloads"];
			if (false === payloadsValue || "object" == typeof payloadsValue && null !== payloadsValue) return true;
		}
		return false;
	}
	withContext(data, fn, options) {
		if (!this.context) return fn();
		return this.context.run(data, fn, options);
	}
	getContext() {
		return this.context?.get();
	}
	enterContext(data, options) {
		this.context?.enter(data, options);
	}
	async _shutdown(shutdownTimeoutMs) {
		const shutdownDeadlineMs = Date.now() + (shutdownTimeoutMs ?? 3e4);
		const resolve = this._consumeWaitUntilCycle();
		await this.featureFlagsPoller?.stopPoller(shutdownTimeoutMs);
		this.errorTracking.shutdown();
		if (this._metrics) {
			await raceWithTimeout(this._metrics.flush().catch(() => {}), Math.max(0, shutdownDeadlineMs - Date.now()));
			this._metrics.reset();
		}
		try {
			return await super._shutdown(Math.max(0, shutdownDeadlineMs - Date.now()));
		} finally {
			this.distinctIdHasSentFlagCalls = {};
			resolve?.();
		}
	}
	async _requestRemoteConfigPayload(flagKey) {
		if (this.disabled || !this.apiKey || !this.options.personalApiKey) return;
		const url = `${this.host}/api/projects/@current/feature_flags/${flagKey}/remote_config?token=${encodeURIComponent(this.apiKey)}`;
		const options = {
			method: "GET",
			headers: {
				...this.getCustomHeaders(),
				"Content-Type": "application/json",
				Authorization: `Bearer ${this.options.personalApiKey}`
			}
		};
		let abortTimeout = null;
		if (this.options.requestTimeout && "number" == typeof this.options.requestTimeout) {
			const controller = new AbortController();
			abortTimeout = safeSetTimeout(() => {
				controller.abort();
			}, this.options.requestTimeout);
			options.signal = controller.signal;
		}
		try {
			return await this.fetch(url, options);
		} catch (error) {
			this._events.emit("error", error);
			return;
		} finally {
			if (abortTimeout) clearTimeout(abortTimeout);
		}
	}
	extractPropertiesFromEvent(eventProperties, groups) {
		if (!eventProperties) return {
			personProperties: {},
			groupProperties: {}
		};
		const personProperties = {};
		const groupProperties = {};
		for (const [key, value] of Object.entries(eventProperties)) if (isPlainObject(value) && groups && key in groups) {
			const groupProps = {};
			for (const [groupKey, groupValue] of Object.entries(value)) groupProps[String(groupKey)] = String(groupValue);
			groupProperties[String(key)] = groupProps;
		} else personProperties[String(key)] = String(value);
		return {
			personProperties,
			groupProperties
		};
	}
	async getFeatureFlagsForEvent(distinctId, groups, disableGeoip, sendFeatureFlagsOptions) {
		if (this.disabled || !this.apiKey) return void this._logger.warn("The client is disabled");
		const finalPersonProperties = sendFeatureFlagsOptions?.personProperties || {};
		const finalGroupProperties = sendFeatureFlagsOptions?.groupProperties || {};
		const flagKeys = sendFeatureFlagsOptions?.flagKeys;
		if (sendFeatureFlagsOptions?.onlyEvaluateLocally ?? this.options.strictLocalEvaluation ?? false) if (!((this.featureFlagsPoller?.featureFlags?.length || 0) > 0)) return {};
		else {
			const groupsWithStringValues = {};
			for (const [key, value] of Object.entries(groups || {})) groupsWithStringValues[key] = String(value);
			return await this.getAllFlags(distinctId, {
				groups: groupsWithStringValues,
				personProperties: finalPersonProperties,
				groupProperties: finalGroupProperties,
				disableGeoip,
				onlyEvaluateLocally: true,
				flagKeys
			});
		}
		if ((this.featureFlagsPoller?.featureFlags?.length || 0) > 0) {
			const groupsWithStringValues = {};
			for (const [key, value] of Object.entries(groups || {})) groupsWithStringValues[key] = String(value);
			return await this.getAllFlags(distinctId, {
				groups: groupsWithStringValues,
				personProperties: finalPersonProperties,
				groupProperties: finalGroupProperties,
				disableGeoip,
				onlyEvaluateLocally: true,
				flagKeys
			});
		}
		return (await super.getFeatureFlagsStateless(distinctId, groups, finalPersonProperties, finalGroupProperties, disableGeoip)).flags;
	}
	addLocalPersonAndGroupProperties(distinctId, groups, personProperties, groupProperties) {
		const allPersonProperties = { ...personProperties || {} };
		const allGroupProperties = {};
		if (groups) for (const groupName of Object.keys(groups)) allGroupProperties[groupName] = {
			$group_key: groups[groupName],
			...groupProperties?.[groupName] || {}
		};
		return {
			allPersonProperties,
			allGroupProperties
		};
	}
	personPropertiesForLocalEvaluation(distinctId, personProperties) {
		return {
			distinct_id: distinctId,
			...personProperties || {}
		};
	}
	createFeatureFlagEvaluationContext(distinctId, groups, personProperties, groupProperties) {
		return {
			distinctId,
			groups: groups || {},
			personProperties: personProperties || {},
			groupProperties: groupProperties || {},
			evaluationCache: {}
		};
	}
	captureException(error, distinctId, additionalProperties, uuid, flags) {
		if (!error_tracking_ErrorTracking.isPreviouslyCapturedError(error)) {
			const syntheticException = /* @__PURE__ */ new Error("PostHog syntheticException");
			this.addPendingPromise(error_tracking_ErrorTracking.buildEventMessage(this.getErrorPropertiesBuilder(), error, { syntheticException }, distinctId, additionalProperties).then((msg) => this._capturePreparedEvent({
				...msg,
				uuid,
				flags
			}, false)));
		}
	}
	async captureExceptionImmediate(error, distinctId, additionalProperties, flags) {
		if (!error_tracking_ErrorTracking.isPreviouslyCapturedError(error)) {
			const syntheticException = /* @__PURE__ */ new Error("PostHog syntheticException");
			return this.addPendingPromise(error_tracking_ErrorTracking.buildEventMessage(this.getErrorPropertiesBuilder(), error, { syntheticException }, distinctId, additionalProperties).then((msg) => this.captureImmediate({
				...msg,
				flags
			})));
		}
	}
	async prepareEventMessage(props) {
		return this._prepareEventMessage(props);
	}
	async _prepareEventMessage(props, options = {}) {
		const { distinctId, event, properties, groups, flags, sendFeatureFlags, timestamp, disableGeoip, uuid } = props;
		const contextData = this.context?.get();
		const includeContextProperties = options.includeContextProperties ?? true;
		let mergedDistinctId = distinctId || contextData?.distinctId;
		const mergedProperties = includeContextProperties ? {
			...this.props,
			...contextData?.properties || {},
			...properties || {}
		} : { ...properties || {} };
		if (!mergedDistinctId) {
			mergedDistinctId = uuidv7();
			mergedProperties.$process_person_profile = false;
		}
		if (includeContextProperties && contextData?.sessionId && !mergedProperties.$session_id) mergedProperties.$session_id = contextData.sessionId;
		const finalProperties = this._shouldSendMinimalFlagCalledEvent(event, mergedProperties) ? minimizeFlagCalledEventProperties(mergedProperties) : mergedProperties;
		const eventMessage = this._runBeforeSend({
			distinctId: mergedDistinctId,
			event,
			properties: finalProperties,
			groups,
			flags,
			sendFeatureFlags,
			timestamp,
			disableGeoip,
			uuid
		});
		if (!eventMessage) return Promise.reject(null);
		const eventProperties = await Promise.resolve().then(async () => {
			if (flags) {
				if (sendFeatureFlags) console.warn("[PostHog] Both `flags` and `sendFeatureFlags` were passed to capture(); using `flags` and ignoring `sendFeatureFlags`.");
				return flags._getEventProperties();
			}
			if (sendFeatureFlags) {
				emitDeprecationWarningOnce("sendFeatureFlags", "`sendFeatureFlags` is deprecated and will be removed in a future major version. Pass a `flags` snapshot from `posthog.evaluateFlags(...)` instead — it avoids a second `/flags` request per capture and guarantees the event carries the exact flag values your code branched on.");
				const sendFeatureFlagsOptions = "object" == typeof sendFeatureFlags ? sendFeatureFlags : void 0;
				return buildFlagEventProperties(await this.getFeatureFlagsForEvent(eventMessage.distinctId, groups, disableGeoip, sendFeatureFlagsOptions));
			}
			return {};
		}).catch(() => ({})).then((additionalProperties) => {
			const resolvedGroups = eventMessage.groups || groups;
			return {
				...additionalProperties,
				...eventMessage.properties || {},
				...void 0 !== resolvedGroups && Object.keys(resolvedGroups).length > 0 ? { $groups: resolvedGroups } : {}
			};
		});
		if ("$pageview" === eventMessage.event && this.options.__preview_capture_bot_pageviews && "string" == typeof eventProperties.$raw_user_agent) {
			if (isBlockedUA(eventProperties.$raw_user_agent, this.options.custom_blocked_useragents || [])) {
				eventMessage.event = "$bot_pageview";
				eventProperties.$browser_type = "bot";
			}
		}
		return {
			distinctId: eventMessage.distinctId,
			event: eventMessage.event,
			properties: eventProperties,
			options: {
				timestamp: eventMessage.timestamp,
				disableGeoip: eventMessage.disableGeoip,
				uuid: eventMessage.uuid
			}
		};
	}
	_runBeforeSend(eventMessage) {
		const beforeSend = this.options.before_send;
		if (!beforeSend) return eventMessage;
		const fns = Array.isArray(beforeSend) ? beforeSend : [beforeSend];
		let result = eventMessage;
		for (const fn of fns) {
			result = fn(result);
			if (!result) {
				this._logger.info(`Event '${eventMessage.event}' was rejected in beforeSend function`);
				return null;
			}
			if (!result.properties || 0 === Object.keys(result.properties).length) {
				const message = `Event '${result.event}' has no properties after beforeSend function, this is likely an error.`;
				this._logger.warn(message);
			}
		}
		return result;
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/context/context.mjs
var PostHogContext = class {
	constructor() {
		this.storage = new AsyncLocalStorage();
	}
	get() {
		return this.storage.getStore();
	}
	run(context, fn, options) {
		return this.storage.run(this.resolve(context, options), fn);
	}
	enter(context, options) {
		this.storage.enterWith(this.resolve(context, options));
	}
	resolve(context, options) {
		if (options?.fresh === true) return context;
		const current = this.get() || {};
		return {
			distinctId: context.distinctId ?? current.distinctId,
			sessionId: context.sessionId ?? current.sessionId,
			properties: {
				...current.properties || {},
				...context.properties || {}
			}
		};
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/extensions/sentry-integration.mjs
const NAME = "posthog-node";
function createEventProcessor(_posthog, { organization, projectId, prefix, severityAllowList = ["error"], sendExceptionsToPostHog = true } = {}) {
	return (event) => {
		if (!("*" === severityAllowList || severityAllowList.includes(event.level))) return event;
		if (!event.tags) event.tags = {};
		const userId = event.tags[PostHogSentryIntegration.POSTHOG_ID_TAG];
		if (void 0 === userId) return event;
		const uiHost = _posthog.options.host ?? "https://us.i.posthog.com";
		const personUrl = new URL(`/project/${_posthog.apiKey}/person/${userId}`, uiHost).toString();
		event.tags["PostHog Person URL"] = personUrl;
		const exceptions = event.exception?.values || [];
		const exceptionList = exceptions.map((exception) => ({
			...exception,
			stacktrace: exception.stacktrace ? {
				...exception.stacktrace,
				type: "raw",
				frames: (exception.stacktrace.frames || []).map((frame) => ({
					...frame,
					platform: "node:javascript"
				}))
			} : void 0
		}));
		const properties = {
			$exception_message: exceptions[0]?.value || event.message,
			$exception_type: exceptions[0]?.type,
			$exception_level: event.level,
			$exception_list: exceptionList,
			$sentry_event_id: event.event_id,
			$sentry_exception: event.exception,
			$sentry_exception_message: exceptions[0]?.value || event.message,
			$sentry_exception_type: exceptions[0]?.type,
			$sentry_tags: event.tags
		};
		const injectedReleaseId = getInjectedReleaseId();
		if (injectedReleaseId) properties.$release_id = injectedReleaseId;
		if (organization && projectId) properties["$sentry_url"] = (prefix || "https://sentry.io/organizations/") + organization + "/issues/?project=" + projectId + "&query=" + event.event_id;
		if (sendExceptionsToPostHog) _posthog.capture({
			event: "$exception",
			distinctId: userId,
			properties
		});
		return event;
	};
}
var PostHogSentryIntegration = class {
	static #_ = this.POSTHOG_ID_TAG = "posthog_distinct_id";
	constructor(_posthog, organization, prefix, severityAllowList, sendExceptionsToPostHog) {
		this.name = NAME;
		this.name = NAME;
		this.setupOnce = function(addGlobalEventProcessor, getCurrentHub) {
			const projectId = getCurrentHub()?.getClient()?.getDsn()?.projectId;
			addGlobalEventProcessor(createEventProcessor(_posthog, {
				organization,
				projectId,
				prefix,
				severityAllowList,
				sendExceptionsToPostHog: sendExceptionsToPostHog ?? true
			}));
		};
	}
};
//#endregion
//#region ../../node_modules/.bun/posthog-node@5.48.0+63120419cc93e79b/node_modules/posthog-node/dist/entrypoints/index.node.mjs
var PostHog = class extends PostHogBackendClient {
	getLibraryId() {
		return "posthog-node";
	}
	initializeContext() {
		return new PostHogContext();
	}
	createErrorPropertiesBuilder() {
		return new ErrorPropertiesBuilder([
			new EventCoercer(),
			new ErrorCoercer(),
			new ObjectCoercer(),
			new StringCoercer(),
			new PrimitiveCoercer()
		], createStackParser("node:javascript", nodeStackLineParser), [
			createModulerModifier(),
			(frames) => addSourceContext(frames, void 0, this._logger),
			createRelativePathModifier()
		]);
	}
};
//#endregion
export { PostHog as t };
