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
  /// The figures are verified and the return has no errors.
  data_sound: boolean;
  /// CRA has certified this build for this return. False for everything this
  /// build can produce today.
  certified_to_file: boolean;
  /// Both. Advisory here and only here — the browser saying a return may be
  /// filed is the browser's opinion about itself, and the server decides at
  /// transmission.
  may_file: boolean;
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
