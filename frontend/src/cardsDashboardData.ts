export type CardProgram = {
  id: "security" | "staff" | "dj" | "artists" | "taxi" | "warehouse" | "bonus" | "zgc" | "partners";
  name: string;
  category: "employees" | "special" | "discount";
  audience?: string;
  topUpAmount?: string;
  topUpPeriod?: string;
  autoTopUp?: boolean;
  resetRule?: string;
  discount: number | null;
  discountNote?: string;
  historical?: boolean;
  comparisonNote?: string;
  notes?: string[];
  companies?: string[];
};

const programs: CardProgram[] = [
  { id: "security", name: "Охрана", category: "employees", audience: "Для сотрудников охраны.", topUpAmount: "1 100 ₽", topUpPeriod: "ежедневно", autoTopUp: true, resetRule: "Перед ежедневным пополнением", discount: 40 },
  { id: "staff", name: "Карта персонала", category: "employees", audience: "Для линейных сотрудников, менеджеров и управляющих.", topUpAmount: "5–30 тыс. ₽", topUpPeriod: "в последний день каждого месяца", autoTopUp: true, resetRule: "Предыдущий остаток обнуляется перед новым ежемесячным пополнением", discount: 40, discountNote: "По умолчанию — на питание сотрудников, по единым правилам скидок.", comparisonNote: "30 000 ₽ — только по согласованию" },
  { id: "dj", name: "DJ", category: "special", topUpAmount: "7 000 ₽", topUpPeriod: "еженедельно", autoTopUp: true, resetRule: "В воскресенье", discount: 40 },
  { id: "artists", name: "Артисты", category: "special", topUpAmount: "2 500 ₽", topUpPeriod: "ежедневно", autoTopUp: true, resetRule: "Через 7 дней от даты начисления", discount: null },
  { id: "taxi", name: "Такси", category: "special", topUpAmount: "5 000 ₽", topUpPeriod: "ежемесячно", discount: null, historical: true, notes: ["Февраль — апрель", "Программа действовала 3 месяца"], comparisonNote: "Февраль — апрель · завершена" },
  { id: "warehouse", name: "Склад", category: "employees", topUpAmount: "500 ₽", topUpPeriod: "ежедневно", autoTopUp: true, resetRule: "Перед каждым пополнением", discount: 40 },
  { id: "bonus", name: "Бонусные карты 40%", category: "discount", audience: "Выдаются индивидуально, когда сотруднику или получателю требуется скидка без автоматического денежного пополнения карты.", autoTopUp: false, discount: 40, notes: ["Выдача — только через согласование."] },
  { id: "zgc", name: "Сотрудники ЗГЦ", category: "employees", topUpAmount: "1 100 ₽", topUpPeriod: "ежедневно", autoTopUp: true, resetRule: "Перед каждым пополнением", discount: 40 },
  { id: "partners", name: "Партнёры", category: "discount", audience: "Для партнёрских компаний.", autoTopUp: false, discount: 25, companies: ["iQos", "My Syberia", "ИП Кузнецова А.А.", "Кант", "Т-Банк"] },
];

export const cardsDashboardData = {
  title: "Карты персонала и бонусные программы",
  subtitle: "Правила начисления, использования, обнуления и согласования",
  summary: [
    { value: String(programs.length), label: "Карточных программ" },
    { value: "40%", label: "Основная скидка" },
    { value: "30 000 ₽", label: "Исключительный лимит", note: "требует согласования" },
    { value: "Юлия", label: "Согласование в будущем сезоне", note: "бонусные карты и исключительный лимит" },
  ],
  programs,
  programGroups: [
    { id: "employees", name: "Карты сотрудников", description: "Лимиты для питания сотрудников и правила их назначения" },
    { id: "special", name: "Специальные программы", description: "Разные периоды пополнения, сроки обнуления и условия скидки" },
    { id: "discount", name: "Скидочные программы без автопополнения", description: "Скидка без автоматического денежного пополнения карты" },
  ],
  globalDiscountRules: {
    title: "Единые правила скидок",
    description: "Для всех программ, предусматривающих скидку, она действует только на:",
    categories: ["Позиции кухни", "Безалкогольный бар"],
    exceptionTitle: "«Напойка»",
    exception: "Скидки не действуют ни по одной программе.",
  },
  staffLimits: [
    { value: "5 000 ₽" }, { value: "7 000 ₽" }, { value: "10 000 ₽" },
    { value: "15 000 ₽" }, { value: "20 000 ₽" }, { value: "30 000 ₽", exceptional: true },
  ],
  staffLimitRules: [
    { amount: "5 000–15 000 ₽", title: "По решению управляющего", description: "Назначаются управляющим по своему усмотрению линейным сотрудникам и менеджерам.", tone: "standard" },
    { amount: "20 000 ₽", title: "Максимальный стандартный лимит", description: "Только для управляющих. Устанавливается им по умолчанию.", tone: "standard" },
    { amount: "30 000 ₽", title: "Исключительный лимит", description: "Не является стандартным. Назначается только после отдельного согласования.", tone: "exception" },
  ],
  staffCycle: { label: "Последний день месяца", steps: ["Остаток", "Обнуление", "Новое пополнение"] },
  staffFlow: { title: "Как работает карта персонала", steps: ["Определение лимита", "Согласование, если 30 000 ₽", "Последний день месяца", "Обнуление остатка", "Автоматическое пополнение", "Использование в течение месяца"] },
  approvalRules: [
    { label: "Ранее", period: "Февраль — апрель", person: "Латиф", historical: true, rules: ["Бонусные карты 40% согласовывались только Латифом.", "Исключительный лимит 30 000 ₽ также согласовывался с Латифом."] },
    { label: "Будущий сезон", period: "Новый порядок", person: "Юлия", historical: false, rules: ["Бонусные карты 40% согласовываются только Юлией.", "Исключительный лимит 30 000 ₽ также согласовывается Юлией."] },
  ],
  conclusion: { title: "Основной принцип", text: "Большинство программ сочетает установленный лимит средств и скидку на питание. Условия различаются по размеру и периодичности пополнения, сроку обнуления, наличию скидки и необходимости согласования.", discount: "Скидки всех программ ограничены кухней и безалкогольным баром и не применяются в «Напойке»." },
};

// Comparison is derived from the same confirmed rules as the program cards.
export function compareProgram(program: CardProgram) {
  return [
    { label: "Пополнение", value: program.topUpAmount ?? (program.autoTopUp === false ? "Нет автопополнения" : "Не указано") },
    { label: "Период", value: program.topUpPeriod ?? "—" },
    { label: "Обнуление", value: program.resetRule ?? (program.autoTopUp === false ? "—" : "Не указано") },
    { label: "Скидка", value: program.discount === null ? "Не предусмотрена" : `${program.discount}%` },
  ];
}

// Existing hash links continue to open the main application views from this URL.
export function isCardsDashboard(location: Pick<Location, "pathname" | "hash">) {
  return location.pathname.replace(/\/$/, "") === "/cards-dashboard" && !location.hash;
}
