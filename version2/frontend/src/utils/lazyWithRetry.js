import { lazy } from "react";

const RETRY_PREFIX = "datasage-lazy-retry:";

const isDynamicImportFetchError = (error) => {
    const message = String(error?.message || error || "");
    return (
        message.includes("Failed to fetch dynamically imported module") ||
        message.includes("Importing a module script failed") ||
        message.includes("ChunkLoadError")
    );
};

export default function lazyWithRetry(importer, key) {
    return lazy(async () => {
        const retryKey = `${RETRY_PREFIX}${key}`;
        const hasRefreshed = sessionStorage.getItem(retryKey) === "true";

        try {
            const module = await importer();
            sessionStorage.setItem(retryKey, "false");
            return module;
        } catch (error) {
            if (!hasRefreshed && isDynamicImportFetchError(error)) {
                sessionStorage.setItem(retryKey, "true");
                window.location.reload();
                return new Promise(() => {});
            }

            sessionStorage.setItem(retryKey, "false");
            throw error;
        }
    });
}
