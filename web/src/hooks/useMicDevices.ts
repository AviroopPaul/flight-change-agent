import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "mic-device-id";

export interface MicDevices {
  /** Audio inputs. Labels stay empty until the page has mic permission. */
  devices: MediaDeviceInfo[];
  /** The chosen device id, or "" for the browser default. */
  deviceId: string;
  /** True once the browser has shown us real device names. */
  labelled: boolean;
  select(id: string): void;
  /** Asks for mic permission once, so the device names become visible. */
  unlock(): Promise<void>;
}

function readSaved(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function save(id: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Storage can be blocked (private mode). The choice then lasts for this page only.
  }
}

async function listInputs(): Promise<MediaDeviceInfo[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const all = await navigator.mediaDevices.enumerateDevices();
  return all.filter((d) => d.kind === "audioinput" && d.deviceId !== "communications");
}

/** Lists the microphones, remembers the choice, and follows plug and unplug events. */
export function useMicDevices(): MicDevices {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState(readSaved);

  const refresh = useCallback(async () => {
    const inputs = await listInputs().catch(() => []);
    setDevices(inputs);
    // A saved device that is gone (unplugged) falls back to the default.
    setDeviceId((current) => (current && inputs.length && !inputs.some((d) => d.deviceId === current) ? "" : current));
  }, []);

  useEffect(() => {
    void refresh();
    const media = navigator.mediaDevices;
    media?.addEventListener?.("devicechange", refresh);
    return () => media?.removeEventListener?.("devicechange", refresh);
  }, [refresh]);

  const select = useCallback((id: string) => {
    setDeviceId(id);
    save(id);
  }, []);

  const unlock = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
    } catch {
      // Permission denied: the list keeps its generic names.
    }
    await refresh();
  }, [refresh]);

  return { devices, deviceId, labelled: devices.some((d) => d.label), select, unlock };
}
