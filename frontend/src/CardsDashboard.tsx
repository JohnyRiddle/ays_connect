import { ArrowRight, Building2, CarTaxiFront, CreditCard, Handshake, History, MicVocal, Music2, Percent, RotateCcw, ShieldCheck, TriangleAlert, UserCheck, Warehouse } from "lucide-react";
import { cardsDashboardData as data, compareProgram, type CardProgram } from "./cardsDashboardData";
import "./cards-dashboard.css";
import { useState } from "react";
import { CardsSeason2027 } from "./CardsSeason2027";
import "./cards-seasons.css";

const icons = { security: ShieldCheck, staff: CreditCard, dj: Music2, artists: MicVocal, taxi: CarTaxiFront, warehouse: Warehouse, bonus: Percent, zgc: Building2, partners: Handshake };

function ProgramCard({ program }: { program: CardProgram }) {
  const Icon = icons[program.id];
  const staff = program.id === "staff";
  return <article className={`cards-panel cards-program${staff ? " cards-program-expanded" : ""}${program.historical ? " cards-historical" : ""}`} data-program={program.id}>
    <div className="cards-program-title">
      <span className="cards-icon"><Icon aria-hidden="true" size={22} /></span>
      <h3>{program.name}</h3>
      {program.historical && <span className="cards-status"><History aria-hidden="true" size={14} />Завершена</span>}
    </div>
    {program.audience && <p className="cards-audience">{program.audience}</p>}
    <div className={staff ? "cards-staff-overview" : undefined}>
      <div>
        {(program.topUpAmount || program.autoTopUp === false) && <p className="cards-amount">{program.topUpAmount ?? "Нет автопополнения"}</p>}
        {program.topUpPeriod && <p className="cards-caption">{program.autoTopUp === true ? "Автоматически, " : ""}{program.topUpPeriod}</p>}
        <dl className="cards-facts">
          {program.resetRule && <div><dt><RotateCcw aria-hidden="true" size={15} />Обнуление</dt><dd>{program.resetRule}</dd></div>}
          <div><dt><Percent aria-hidden="true" size={15} />Скидка</dt><dd><span className={`cards-discount-value${program.discount === null ? " cards-no-discount" : ""}`}>{program.discount === null ? "Не предусмотрена" : `${program.discount}%`}</span>{program.discountNote && <p className="cards-caption">{program.discountNote}</p>}{program.discount !== null && !program.discountNote && <span className="cards-discount-scope">По единым правилам скидок</span>}</dd></div>
        </dl>
      </div>
      {staff && <div className="cards-staff-cycle">
        <h4>Месячные лимиты</h4>
        <ul className="cards-limits" aria-label="Месячные лимиты">{data.staffLimits.map(limit => <li className={limit.exceptional ? "cards-chip-exception" : undefined} key={limit.value}>{limit.value}{limit.exceptional && <UserCheck aria-hidden="true" size={14} />}</li>)}</ul>
        <p className="cards-cycle-label">{data.staffCycle.label}</p>
        <ol className="cards-cycle">{data.staffCycle.steps.map((step, index) => <li key={step}>{index > 0 && <ArrowRight aria-hidden="true" size={16} />}<span>{step}</span></li>)}</ol>
      </div>}
    </div>
    {program.notes && <div className="cards-notes">{program.notes.map(note => <p key={note}>{note}</p>)}</div>}
    {program.companies && <ul className="cards-limits cards-companies" aria-label="Партнёрские компании">{program.companies.map(company => <li key={company}>{company}</li>)}</ul>}
    {staff && <>
      <div className="cards-limit-rules">{data.staffLimitRules.map(rule => <div key={rule.amount} className={`cards-limit-rule cards-limit-${rule.tone}`}><p className="cards-limit-amount">{rule.amount}</p><h4>{rule.title}</h4><p>{rule.description}</p></div>)}</div>
      <div className="cards-staff-flow"><h4>{data.staffFlow.title}</h4><ol className="cards-flow">{data.staffFlow.steps.map((step, index) => <li key={step}><span className="cards-step">{index + 1}</span><span>{step}</span>{index < data.staffFlow.steps.length - 1 && <ArrowRight className="cards-flow-arrow" aria-hidden="true" size={18} />}</li>)}</ol></div>
    </>}
  </article>;
}

function CardsSeason2526() {
  return <main className="dashboard cards-dashboard">
    <div className="cards-heading"><p className="eyebrow blue">AYS Connect</p><h1>{data.title}</h1><p>{data.subtitle}</p></div>
    <dl className="cards-summary">{data.summary.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd>{item.note && <small>{item.note}</small>}</div>)}</dl>

    <section className="cards-panel cards-discount" aria-labelledby="cards-discount-title">
      <div className="cards-section-title"><Percent aria-hidden="true" size={22} /><h2 id="cards-discount-title">{data.globalDiscountRules.title}</h2></div>
      <div className="cards-discount-layout"><div><p>{data.globalDiscountRules.description}</p><ul>{data.globalDiscountRules.categories.map(category => <li key={category}>{category}</li>)}</ul></div>
        <aside className="cards-warning" aria-labelledby="cards-exception"><TriangleAlert aria-hidden="true" size={24} /><div><h3 id="cards-exception">{data.globalDiscountRules.exceptionTitle}</h3><p>{data.globalDiscountRules.exception}</p></div></aside>
      </div>
    </section>

    {data.programGroups.map((group, index) => {
      const programs = data.programs.filter(program => program.category === group.id).sort((a, b) => Number(b.id === "staff") - Number(a.id === "staff"));
      return <section className="cards-group" key={group.id} aria-labelledby={`cards-group-${group.id}`}>
        <div className="cards-group-heading"><span className="cards-group-number">0{index + 1}</span><div><h2 id={`cards-group-${group.id}`}>{group.name}</h2><p>{group.description}</p></div><span className="cards-group-count">{programs.length}</span></div>
        <div className={`cards-program-grid cards-group-${group.id}`}>{programs.map(program => <ProgramCard key={program.id} program={program} />)}</div>
      </section>;
    })}

    <section aria-labelledby="cards-comparison-title">
      <h2 id="cards-comparison-title">Сравнение программ</h2>
      <div className="cards-panel cards-comparison-desktop"><table className="cards-comparison-table">
        <caption>Условия пополнения, обнуления и скидки по всем девяти программам</caption>
        <thead><tr><th scope="col">Программа</th>{compareProgram(data.programs[0]).map(field => <th scope="col" key={field.label}>{field.label}</th>)}</tr></thead>
        <tbody>{data.programs.map(program => <tr key={program.id}><th scope="row">{program.name}{program.comparisonNote && <small>{program.comparisonNote}</small>}</th>{compareProgram(program).map(field => <td key={field.label}>{field.value}</td>)}</tr>)}</tbody>
      </table></div>
      <details className="cards-panel cards-comparison-mobile"><summary>Сравнить все программы</summary><div className="cards-comparison-list">{data.programs.map(program => <article key={program.id}><h3>{program.name}</h3>{program.comparisonNote && <p className="cards-caption">{program.comparisonNote}</p>}<dl>{compareProgram(program).map(field => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl></article>)}</div></details>
    </section>

    <section aria-labelledby="cards-approval">
      <div className="cards-section-title"><UserCheck aria-hidden="true" size={22} /><h2 id="cards-approval">Кто согласовывает</h2></div>
      <div className="cards-approvals">{data.approvalRules.map(rule => <article key={rule.label} className={`cards-panel cards-approval ${rule.historical ? "cards-historical" : "cards-future"}`}><h3>{rule.label}</h3><p className="cards-caption">{rule.period}</p><p className="cards-person">{rule.person}</p>{rule.rules.map(text => <p className="cards-approval-note" key={text}>{text}</p>)}</article>)}</div>
    </section>
    <section className="cards-conclusion" aria-labelledby="cards-principle"><h2 id="cards-principle">{data.conclusion.title}</h2><p>{data.conclusion.text}</p><p>{data.conclusion.discount}</p></section>
  </main>;
}

export function CardsDashboard() {
  const [season, setSeason] = useState<"25-26" | "2027">("2027");
  const seasons = [{ id: "25-26", title: "Сезон 25-26" }, { id: "2027", title: "Сезон 2027" }] as const;
  return <div className="cards-seasons">
    <div className="cards-season-tabs" role="tablist" aria-label="Сезон правил работы с картами">
      {seasons.map(item => <button key={item.id} type="button" role="tab" id={`season-tab-${item.id}`}
        aria-selected={season === item.id} aria-controls={`season-panel-${item.id}`} tabIndex={season === item.id ? 0 : -1}
        onClick={() => setSeason(item.id)} onKeyDown={event => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            event.preventDefault();
            const next = event.key === "Home" ? "25-26" : event.key === "End" ? "2027" : season === "2027" ? "25-26" : "2027";
            setSeason(next); document.getElementById(`season-tab-${next}`)?.focus();
          }
        }}>{item.title}</button>)}
    </div>
    <div id="season-panel-25-26" role="tabpanel" aria-labelledby="season-tab-25-26" hidden={season !== "25-26"}><CardsSeason2526 /></div>
    <div id="season-panel-2027" role="tabpanel" aria-labelledby="season-tab-2027" hidden={season !== "2027"}><CardsSeason2027 /></div>
  </div>;
}
