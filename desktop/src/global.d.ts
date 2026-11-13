export {};

declare global {
  interface Window {
    hive: {
      send: (msg: unknown) => void;
      ready: () => void;
      restart: () => Promise<{ ok: boolean }>;
      onEvent: (cb: (msg: any) => void) => () => void;
      onLog: (cb: (line: string) => void) => () => void;
      onExit: (cb: (info: any) => void) => () => void;
    };
  }
}
