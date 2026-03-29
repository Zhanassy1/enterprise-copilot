/** Локализованное форматирование чисел и объёма для квот (billing UI). */

export function formatQuotaNumber(n: number): string {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.max(0, Math.floor(n)));
}

export function formatBytesIEC(n: number): string {
  const v = Math.max(0, n);
  if (v === 0) return "0 B";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let x = v;
  let i = 0;
  while (x >= 1024 && i < units.length - 1) {
    x /= 1024;
    i++;
  }
  const digits = i === 0 ? 0 : x >= 10 ? 0 : 1;
  return `${x.toFixed(digits)} ${units[i]}`;
}
