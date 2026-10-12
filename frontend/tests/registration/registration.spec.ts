import {test,expect} from "@playwright/test";

const backend = process.env.REGISTRATION_BACKEND_URL || "http://127.0.0.1:18043";
const location = process.env.REGISTRATION_TEST_LOCATION!;
const role = process.env.REGISTRATION_TEST_ROLE!;
const password = "Synthetic-Browser-2026!";
test.beforeAll(()=>{
  if(backend!=="http://127.0.0.1:18043" || process.env.DATABASE_URL!=="postgresql://registration_test@127.0.0.1:55443/registration") throw new Error("Only isolated synthetic registration database is allowed");
});
async function ownerToken(request:any){
  const response=await request.post(backend+"/api/v1/auth/login/",{data:{email:"browser-owner@synthetic.test",password}});
  expect(response.status()).toBe(200);
  return (await response.json()).access;
}
for(const scenario of ["self","invite"]){
  test(`${scenario}: direct submission, approval, scoped working access`,async({page,request},testInfo)=>{
    const email=`${scenario}-${testInfo.project.name}-${Date.now()}@synthetic.test`;
    const token=await ownerToken(request);
    const headers={Authorization:`Bearer ${token}`};
    let invite="";
    if(scenario==="invite"){
      const response=await request.post(backend+"/api/internal/v1/registration/invitations/",{headers,data:{location,email,plan:{role,access_locations:[location],responsibility_mode:"selected",responsibility_locations:[location]}}});
      expect(response.status()).toBe(201);
      invite=(await response.json()).invitation_url.split("#invite=")[1];
    }
    const errors:string[]=[]; page.on("pageerror",e=>errors.push(e.message));
    await page.goto(`/register${invite?`#invite=${invite}`:""}`);
    await page.getByLabel("Фамилия",{exact:true}).fill("Синтетический");
    await page.getByLabel("Имя",{exact:true}).fill("Тест");
    await page.getByLabel("E-mail",{exact:true}).fill(email);
    if(scenario==="self")await page.getByRole("combobox",{name:"Объект трудоустройства",exact:true}).selectOption(location);
    else await expect(page.getByText("Browser registration object",{exact:true})).toBeVisible();
    await page.getByLabel("Пароль",{exact:true}).fill(password);
    await page.getByLabel("Подтверждение пароля",{exact:true}).fill(password);
    await page.getByRole("button",{name:"Зарегистрироваться",exact:true}).click();
    await expect(page.getByRole("heading",{name:scenario==="self"?"Ожидает согласования":"Одобрена",exact:true})).toBeVisible();
    if(scenario==="self"){
      const before=await request.post(backend+"/api/v1/auth/login/",{data:{email,password}});
      expect(before.status()).toBe(401);
    }
    if(scenario==="self"){
      const list=await request.get(backend+"/api/internal/v1/registration/requests/",{headers});
      const data=await list.json(); const item=(data.results||data).find((x:any)=>x.email===email);
      expect(item).toBeTruthy();
      const approved=await request.post(backend+`/api/internal/v1/registration/requests/${item.id}/approve/`,{headers,data:{plan:{role,access_locations:[location],responsibility_mode:"selected",responsibility_locations:[]}}});
      expect(approved.status()).toBe(200);
      await page.getByRole("button",{name:"Обновить статус"}).click();
      await expect(page.getByRole("heading",{name:"Одобрена",exact:true})).toBeVisible();
    }
    const login=await request.post(backend+"/api/v1/auth/login/",{data:{email,password}});
    expect(login.status()).toBe(200);
    const access=(await login.json()).access;
    const detail=await request.get(backend+`/api/internal/v1/objects/${location}/`,{headers:{Authorization:`Bearer ${access}`}});
    expect(detail.status()).toBe(200);
    const width=await page.evaluate(()=>({body:document.documentElement.scrollWidth,viewport:innerWidth}));
    expect(width.body).toBeLessThanOrEqual(width.viewport);
    expect(errors).toEqual([]);
  });
}

test("management UI creates and revokes an invite",async({page,request})=>{
  const token=await ownerToken(request);
  await page.goto("/register");
  await page.evaluate(token=>sessionStorage.setItem("access",token),token);
  await page.goto("/people/registration");
  await expect(page.getByRole("heading",{name:"Регистрация и приглашения",exact:true})).toBeVisible();
  await page.getByRole("combobox",{name:"Объект",exact:true}).first().selectOption(location);
  await page.getByLabel("E-mail получателя (необязательно)").fill(`managed-${Date.now()}@synthetic.test`);
  await page.getByRole("button",{name:"Создать приглашение",exact:true}).click();
  await expect(page.getByLabel("Одноразовая ссылка")).toHaveValue(/#invite=/);
  const newest=page.locator("article").filter({hasText:"managed-"}).first();
  await newest.getByRole("button",{name:"Отозвать",exact:true}).click();
  await expect(newest).toContainText("revoked");
});
