export interface Line {
  id: string;
  label: string;
  value: string;
  note: string | null;
}

export interface Diagnostic {
  id: string;
  severity: "error" | "warning" | "info";
  message: string;
  help: string | null;
}

export interface Computed {
  lines: Line[];
  diagnostics: Diagnostic[];
  /// Parameters not yet checked against a published source.
  warnings: string[];
  has_errors: boolean;
  /// Advisory here, and only here. The browser saying a return is filable is
  /// the browser's opinion about itself; the server decides at transmission.
  filable: boolean;
}

export interface Capabilities {
  years: number[];
  provinces: string[];
  t2_provinces: string[];
  certification_target_year: number;
  certified_years: number[];
}

export interface Period {
  start: string;
  end: string;
}
