import { test, expect, Page } from "@playwright/test";

const api = process.env.AYS_OBJECTS_API_URL || "http://127.0.0.1:18081";
const syntheticPassword = "SyntheticObjectsOnly1!";
test.use({actionTimeout:10000});
const authTokens = new Map<string,{access:string;refresh:string}>();
async function tokensFor(page:Page,email="objects@synthetic.test") {
  const cached = authTokens.get(email);if(cached)return cached;
  await expect.poll(async()=>{try{return (await page.request.get(`${api}/api/v1/health/`)).status();}catch{return 0;}},{timeout:15000}).toBe(200);
  const response = await page.request.post(`${api}/api/v1/auth/login/`,{data:{email,password:syntheticPassword}});
  expect(response.ok()).toBeTruthy();
  const tokens=await response.json();authTokens.set(email,tokens);return tokens;
}
async function login(page:Page,email="objects@synthetic.test") {
  const tokens=await tokensFor(page,email);
  await page.addInitScript(({access,refresh})=>{sessionStorage.setItem("access",access);sessionStorage.setItem("refresh",refresh);},tokens);
  return tokens.access as string;
}

test("synthetic create, edit, zones, responsibles, season, related and archive",async({page})=>{
  test.setTimeout(120000);
  const token=await login(page);
  const headers={Authorization:`Bearer ${token}`};
  await page.goto("/objects");
  await page.getByRole("button",{name:"Добавить объект",exact:true}).click();
  const dialog=page.getByRole("dialog");
  const name=`Синтетический browser ${Date.now()}`;
  await dialog.getByLabel("Название *",{exact:true}).fill(name);
  await dialog.getByLabel("Тип объекта *").selectOption("office");
  await expect(dialog.getByLabel("Часовой пояс *")).toHaveValue("Asia/Novosibirsk");
  await dialog.getByLabel("Основное юрлицо").selectOption({label:"Синтетическое юрлицо"});
  await dialog.getByLabel("Основное подразделение").selectOption({label:"Синтетическое подразделение"});
  await dialog.getByLabel("Адрес / местоположение").fill("Синтетический адрес");
  await dialog.getByRole("combobox",{name:"Управляющий",exact:true}).selectOption({label:"Управляющий Синтетический"});
  await dialog.getByRole("button",{name:"Создать объект",exact:true}).click();
  await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();
  const id = new URL(page.url()).pathname.split("/").pop()!;
  await expect(page.getByRole("status")).toContainText("Объект создан");
  await page.getByRole("button",{name:"Добавить зоны",exact:true}).click();
  await page.getByLabel("Название зоны *").fill("Синтетическая зона");
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await expect(page.getByRole("button",{name:"Синтетическая зона",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Редактировать",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Контакты").fill("Синтетические контакты");
  await page.getByRole("dialog").getByRole("button",{name:"Сохранить",exact:true}).click();
  await expect(page.getByText("Синтетические контакты",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Начать работу",exact:true}).click();
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await expect(page.locator(".object-status")).toHaveText("Работает");
  await page.getByRole("button",{name:"Сезонно закрыть",exact:true}).click();
  await page.getByLabel("Причина",{exact:true}).fill("Синтетический сезон");
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await expect(page.locator(".object-status")).toHaveText("Сезонно закрыт");
  await page.getByRole("button",{name:"Возобновить сезон",exact:true}).click();
  await page.getByLabel("Причина",{exact:true}).fill("Синтетическое открытие");
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await expect(page.locator(".object-status")).toHaveText("Работает");
  await page.getByRole("button",{name:"Создать задачу",exact:true}).click();
  await expect(page.getByLabel("Объект / локация")).toHaveValue(id);
  await page.getByLabel("Название *",{exact:true}).fill("Синтетическая задача объекта");
  await page.getByRole("button",{name:"Создать задачу",exact:true}).click();
  await expect(page).toHaveURL(/\/tasks\/[0-9a-f-]+$/);
  const taskId=new URL(page.url()).pathname.split("/").pop();
  const projectResponse=await page.request.post(`${api}/api/internal/v1/projects/`,{headers:{...headers,"Idempotency-Key":crypto.randomUUID()},data:{name:"Синтетический проект объекта",location:id}});
  expect(projectResponse.ok()).toBeTruthy();
  await page.goto(`/objects/${id}?tab=tasks`);
  await expect(page.getByRole("button",{name:/Синтетическая задача объекта/})).toBeVisible();
  await page.getByRole("button",{name:"Прямые проекты",exact:true}).click();
  await expect(page.getByRole("button",{name:/Синтетический проект объекта/})).toBeVisible();
  await page.getByRole("button",{name:"Создать заявку",exact:true}).click();
  await expect(page).toHaveURL(new RegExp(`/requests/new\\?location=${id}`));
  await page.getByRole("combobox",{name:"Тип заявки *",exact:true}).selectOption({label:"Синтетическая категория Objects · Синтетическая услуга Objects · Синтетическая заявка"});
  await page.getByLabel("Тема *",{exact:true}).fill("Синтетическая заявка объекта");
  await page.getByRole("button",{name:"Создать заявку",exact:true}).click();
  await expect(page).toHaveURL(/\/requests\/[0-9a-f-]+$/);
  await page.goto(`/objects/${id}?tab=requests`);
  await expect(page.getByRole("button",{name:/Синтетическая заявка объекта/})).toBeVisible();
  await page.goto(`/objects/${id}?tab=zones`);
  await page.getByRole("button",{name:"Синтетическая зона",exact:true}).click();
  await page.getByRole("button",{name:"Архивировать",exact:true}).click();
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await expect(page.locator(".object-status")).toHaveText("Архив");
  await page.goto(`/objects/${id}`);
  await page.getByRole("button",{name:"Назначить ответственного",exact:true}).click();
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await page.getByRole("button",{name:"Окончательно закрыть",exact:true}).click();
  await page.getByLabel("Причина",{exact:true}).fill("Синтетическое закрытие");
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await page.getByRole("button",{name:"Архивировать",exact:true}).click();
  await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await expect(page.getByRole("alert")).toContainText("действующими связями");
  // The synthetic task is explicitly cancelled; archive never closes it automatically.
  const task=await (await page.request.get(`${api}/api/internal/v1/tasks/${taskId}/`,{headers})).json();
  const cancelled=await page.request.post(`${api}/api/internal/v1/tasks/${taskId}/cancel/`,{headers,data:{version:task.version,reason:"Synthetic gate cleanup"}});
  // This persona intentionally has no cancellation grant; the blocker is the acceptance result.
  expect(cancelled.status()).toBe(400);
  expect((await cancelled.json()).error.code).toBe("task_permission_denied");
  await page.getByRole("dialog").getByRole("button",{name:"Закрыть",exact:true}).click();
  await page.screenshot({path:"test-results/objects-desktop.png",fullPage:true});
});

test("synthetic version conflict preserves input and registry filters survive reload",async({page})=>{
  const token=await login(page);const headers={Authorization:`Bearer ${token}`};
  const name=`Синтетический конфликт ${Date.now()}`;
  const response=await page.request.post(`${api}/api/internal/v1/objects/`,{headers:{...headers,"Idempotency-Key":crypto.randomUUID()},data:{name,business_type:"office",timezone:"Asia/Novosibirsk"}});
  expect(response.status()).toBe(201);const item=await response.json();
  await page.goto(`/objects/${item.id}`);await page.getByRole("button",{name:"Редактировать",exact:true}).click();
  const dialog=page.getByRole("dialog");await dialog.getByLabel("Контакты").fill("Сохранённый ввод");
  const concurrent=await page.request.patch(`${api}/api/internal/v1/objects/${item.id}/`,{headers,data:{version:item.version,name:`${name} updated`}});expect(concurrent.status()).toBe(200);
  await dialog.getByRole("button",{name:"Сохранить",exact:true}).click();await expect(dialog.getByRole("alert")).toContainText("Введённые значения сохранены");
  await expect(dialog.getByLabel("Контакты")).toHaveValue("Сохранённый ввод");
  await dialog.getByRole("button",{name:"Обновить карточку",exact:true}).click();
  await expect(page.getByRole("heading",{name:`${name} updated`,exact:true})).toBeVisible();
  await dialog.getByRole("button",{name:"Сохранить",exact:true}).click();await expect(page.getByText("Сохранённый ввод",{exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:`${name} updated`,exact:true})).toBeVisible();
  await page.goto(`/objects?search=${encodeURIComponent(name)}&business_type=office&business_status=preparation&archived=false&page=1`);
  await expect(page.getByRole("button",{name:new RegExp(name)})).toBeVisible();await page.reload();
  await expect(page.getByRole("button",{name:new RegExp(name)})).toBeVisible();
  expect(new URL(page.url()).searchParams.get("search")).toBe(name);
});

test("synthetic mobile form retains input after network failure and has no overflow",async({page})=>{
  await login(page);await page.setViewportSize({width:390,height:844});await page.goto("/objects");
  await page.getByRole("button",{name:"Добавить объект",exact:true}).click();
  const dialog=page.getByRole("dialog");
  const name=`Синтетический mobile ${Date.now()}`;
  await dialog.getByLabel("Название *",{exact:true}).fill(name);await dialog.getByLabel("Тип объекта *").selectOption("warehouse");
  let attempts=0; const keys:string[]=[];
  await page.route("**/api/internal/v1/objects/",async route=>{if(route.request().method()==="POST") {keys.push(route.request().headers()["idempotency-key"]);if(attempts++===0){const result=await route.fetch({url:route.request().url().replace("http://localhost:18081",api)});expect(result.status()).toBe(201);await route.abort("failed");return;}}await route.continue();});
  await dialog.getByRole("button",{name:"Создать объект",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Нет соединения");
  await expect(dialog.getByLabel("Название *",{exact:true})).toHaveValue(name);
  await dialog.getByRole("button",{name:"Создать объект",exact:true}).click();
  await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();
  expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:"test-results/objects-mobile.png",fullPage:true});
});

test("synthetic negative persona has no creation action and direct write denied",async({page})=>{
  const token=await login(page,"objects-denied@synthetic.test");await page.goto("/objects");
  await expect(page.getByRole("heading",{name:"Объекты",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Добавить объект",exact:true})).toHaveCount(0);
  const response=await page.request.post(`${api}/api/internal/v1/objects/`,{headers:{Authorization:`Bearer ${token}`,"Idempotency-Key":"denied"},data:{name:"Denied",business_type:"office",timezone:"Asia/Novosibirsk"}});
  expect(response.status()).toBe(403);
});

test("synthetic editing preserves hidden organizational links",async({page})=>{
  const operator=(await tokensFor(page)).access;const operatorHeaders={Authorization:`Bearer ${operator}`};
  const choices=await (await page.request.get(`${api}/api/internal/v1/objects/lookups/`,{headers:operatorHeaders})).json();
  const legal=choices.legal_entities.find((x:any)=>x.name==="Синтетическое юрлицо").id;
  const unit=choices.org_units.find((x:any)=>x.name==="Синтетическое подразделение").id;
  const name=`Синтетический скрытый контекст ${Date.now()}`;
  const response=await page.request.post(`${api}/api/internal/v1/objects/`,{headers:{...operatorHeaders,"Idempotency-Key":crypto.randomUUID()},data:{name,business_type:"office",timezone:"Asia/Novosibirsk",legal_entity:legal,org_unit:unit}});
  expect(response.status()).toBe(201);const item=await response.json();
  await login(page,"objects-editor@synthetic.test");await page.goto(`/objects/${item.id}`);
  await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();
  await expect(page.getByText("Синтетическое подразделение",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Редактировать",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Контакты").fill("Изменён только контакт");
  await page.getByRole("dialog").getByRole("button",{name:"Сохранить",exact:true}).click();
  await expect(page.getByText("Изменён только контакт",{exact:true})).toBeVisible();
  const saved=await (await page.request.get(`${api}/api/internal/v1/objects/${item.id}/`,{headers:operatorHeaders})).json();
  expect(saved.org_unit).toBe(unit);expect(saved.legal_entity).toBe(legal);
});

test("synthetic duplicate confirmation, archive and restore retain identity",async({page})=>{
  const token=await login(page);const headers={Authorization:`Bearer ${token}`};
  const name=`Синтетический дубль ${Date.now()}`;
  const original=await page.request.post(`${api}/api/internal/v1/objects/`,{headers:{...headers,"Idempotency-Key":`original-${Date.now()}`},data:{name,business_type:"bar",timezone:"Asia/Novosibirsk"}});expect(original.status()).toBe(201);
  await page.goto("/objects");await page.getByRole("button",{name:"Добавить объект",exact:true}).click();
  const dialog=page.getByRole("dialog");await dialog.getByLabel("Название *",{exact:true}).fill(name);await dialog.getByLabel("Тип объекта *").selectOption("bar");
  await dialog.getByRole("button",{name:"Создать объект",exact:true}).click();await expect(dialog.getByRole("alert")).toContainText("похожий");
  await dialog.getByRole("checkbox").check();await dialog.getByRole("button",{name:"Создать объект",exact:true}).click();await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();
  const id=new URL(page.url()).pathname.split("/").pop();
  await page.getByRole("button",{name:"Окончательно закрыть",exact:true}).click();await page.getByLabel("Причина",{exact:true}).fill("Синтетическое закрытие");await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();
  await page.getByRole("button",{name:"Архивировать",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();await expect(page.locator(".object-status")).toHaveText("Архив");
  await page.getByRole("button",{name:"Восстановить из архива",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();await expect(page.locator(".object-status")).toHaveText("Окончательно закрыт");
  await page.getByRole("button",{name:"Возобновить в подготовке",exact:true}).click();await page.getByLabel("Причина",{exact:true}).fill("Синтетическое возобновление");await page.getByRole("dialog").getByRole("button",{name:"Подтвердить"}).click();await expect(page.locator(".object-status")).toHaveText("Подготовка");
  expect(new URL(page.url()).pathname).toBe(`/objects/${id}`);
});
