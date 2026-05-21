import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import planningWithFilesExtension from "./runtime.ts";

export default function (pi: ExtensionAPI): void {
	planningWithFilesExtension(pi);
}
