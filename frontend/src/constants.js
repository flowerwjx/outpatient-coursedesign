export const DEPARTMENTS = Object.freeze([
  "内科",
  "外科",
  "儿科",
  "妇产科",
  "中医科",
  "眼科",
  "耳鼻喉科",
  "口腔科",
  "皮肤科",
  "急诊科",
]);

export const ROLE_LABELS = Object.freeze({
  admin: "系统管理员",
  doctor: "门诊医生",
  cashier: "收费员",
  pharmacist: "药房药师",
});

export const REGISTRATION_STATUS_LABELS = Object.freeze({
  registered: "已挂号",
  cancelled: "已取消",
});

export function formatDate(value) {
  if (!value) {
    return "-";
  }
  return String(value).slice(0, 10);
}

export function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value).replace("T", " ").slice(0, 19);
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}
