import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir:"./tests/registration", timeout:45000, workers:1,
  outputDir:process.env.REGISTRATION_BROWSER_OUTPUT || "test-results/registration",
  use:{baseURL:process.env.REGISTRATION_BROWSER_URL||"http://127.0.0.1:13043",trace:"off"},
  projects:[{name:"desktop",use:{viewport:{width:1440,height:1000}}},
            {name:"mobile",use:{viewport:{width:390,height:844}}}]
});
