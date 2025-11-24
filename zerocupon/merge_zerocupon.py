import os
import re
import zipfile
from io import StringIO

import pandas as pd


def _read_table_from_zip(zip_path: str) -> pd.DataFrame:
	"""Read a single-CSV ZIP, skip preamble lines, return a 3-column DataFrame."""
	with zipfile.ZipFile(zip_path, "r") as zf:
		# pick the first CSV file inside the archive
		csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
		if not csv_names:
			raise ValueError(f"No CSV file found inside: {zip_path}")
		member = csv_names[0]

		raw = zf.read(member)

		# try encodings
		text = None
		for enc in ("utf-8-sig", "cp1251"):
			try:
				text = raw.decode(enc)
				break
			except UnicodeDecodeError:
				continue
		if text is None:
			# fallback
			text = raw.decode("utf-8", errors="replace")

		lines = text.splitlines()
		header_pattern = re.compile(r"^\s*tradedate\s*;\s*tradetime\s*;\s*period_\d+(?:\.\d+)?\s*$", re.IGNORECASE)

		header_idx = None
		for idx, line in enumerate(lines):
			if header_pattern.match(line):
				header_idx = idx
				break
		if header_idx is None:
			raise ValueError(f"CSV header not found in: {zip_path}")

		clean_text = "\n".join(lines[header_idx:])
		df = pd.read_csv(StringIO(clean_text), sep=";", engine="python")

		# enforce exactly 3 columns presence
		if df.shape[1] < 3:
			raise ValueError(f"Unexpected CSV structure in: {zip_path}")
		return df.iloc[:, :3]


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
	"""Rename columns to русские названия as required."""
	columns = list(df.columns)
	if len(columns) < 3:
		raise ValueError("DataFrame must have at least 3 columns")
	base_name = str(columns[2])

	# Extract X.Y from 'period_X.Y'
	m = re.search(r"period_(\d+(?:\.\d+)?)", base_name, flags=re.IGNORECASE)
	term_label = f"Срок {m.group(1)} лет" if m else base_name

	renamed = df.rename(
		columns={
			columns[0]: "Дата",
			columns[1]: "Время",
			columns[2]: term_label,
		}
	)
	return renamed


def main() -> None:
	script_dir = os.path.abspath(os.path.dirname(__file__))

	# collect ZIPs in the same folder
	zip_files = [os.path.join(script_dir, f) for f in os.listdir(script_dir) if f.lower().endswith(".zip")]
	if not zip_files:
		raise SystemExit("ZIP archives not found in the @zerocupon folder.")

	# deterministic order
	zip_files.sort(key=lambda p: os.path.basename(p).lower())

	# base DataFrame from the first ZIP (keep 3 columns, then rename)
	base_df_raw = _read_table_from_zip(zip_files[0])
	base_df = _rename_columns(base_df_raw)

	# for the rest: take only the 3rd column and merge by ('дата','время')
	for zpath in zip_files[1:]:
		df_raw = _read_table_from_zip(zpath)
		df_named = _rename_columns(df_raw)

		term_col_candidates = [c for c in df_named.columns if c not in ("Дата", "Время")]
		if not term_col_candidates:
			continue
		term_col = term_col_candidates[0]

		to_join = df_named[["Дата", "Время", term_col]]
		base_df = base_df.merge(to_join, on=["Дата", "Время"], how="outer")

	# Save result CSV in the same folder
	out_path = os.path.join(script_dir, "zerocupon.csv")

	# normalize date and time columns to DD.MM.YYYY and HH:MM:SS
	if "Дата" in base_df.columns:
		_dt = pd.to_datetime(base_df["Дата"], dayfirst=True, errors="coerce")
		base_df["Дата"] = _dt.dt.strftime("%d.%m.%Y")
	if "Время" in base_df.columns:
		_tm = pd.to_datetime(base_df["Время"], format="%H:%M:%S", errors="coerce")
		base_df["Время"] = _tm.dt.strftime("%H:%M:%S")

	# normalize period columns: convert to numeric (handle commas/spaces/dashes)
	for col in [c for c in base_df.columns if c not in ("Дата", "Время")]:
		series = base_df[col]
		if pd.api.types.is_numeric_dtype(series):
			continue
		series = series.astype(str).str.strip()
		series = series.replace({"": None, "-": None})
		series = series.str.replace(" ", "", regex=False)
		series = series.str.replace(",", ".", regex=False)
		base_df[col] = pd.to_numeric(series, errors="coerce")

	# sort term columns (exclude 'Дата','Время') by numeric maturity ascending
	term_cols = [c for c in base_df.columns if c not in ("Дата", "Время")]
	def _term_key(col_name: str) -> float:
		m = re.search(r"Срок\s+(\d+(?:\.\d+)?)\s+лет", str(col_name))
		return float(m.group(1)) if m else float("inf")
	term_cols_sorted = sorted(term_cols, key=_term_key)
	col_order = ["Дата", "Время"] + term_cols_sorted
	base_df = base_df[col_order]

	# sort rows by 'дата' descending (parse as date, day-first tolerant)
	base_df = base_df.sort_values(
		by="Дата",
		ascending=False,
		key=lambda s: pd.to_datetime(s, dayfirst=True, errors="coerce"),
	)

	base_df.to_csv(out_path, index=False, sep=";")


if __name__ == "__main__":
	main()


