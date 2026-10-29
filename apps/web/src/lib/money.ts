export function rupees(amount: number | null) {
  return amount === null
    ? "Not calculated"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(amount);
}
