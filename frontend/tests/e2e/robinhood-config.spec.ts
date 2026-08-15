import { expect, test } from "@playwright/test";

const session = process.env.AEGIS_TEST_SESSION;
test.skip(!session, "Requires an ephemeral server-side acceptance session");

test("authenticated operator can save only official non-secret Robinhood MCP metadata", async ({ context, page }) => {
  await context.addCookies([{name:"aegis_session",value:session!,domain:"aegis-alpha.pacificao.com",path:"/",httpOnly:true,secure:true,sameSite:"Strict"}]);
  await page.goto("/system");
  await expect(page.getByRole("heading",{name:"Robinhood Trading MCP"})).toBeVisible();
  await expect(page.getByRole("button",{name:"CONNECT ROBINHOOD IN BROWSER"})).toBeDisabled();
  await expect(page.getByText("Authorization is disabled on this development host",{exact:false})).toBeVisible();
  await expect(page.getByText("rejects all order",{exact:false})).toBeVisible();
  await expect(page.getByText("Never enter a Robinhood password, token, API key, or private key",{exact:false})).toBeVisible();
  await expect(page.getByLabel("Official MCP endpoint")).toHaveValue("https://agent.robinhood.com/mcp/trading");
  await page.getByLabel("Connection name").fill("Nathan Robinhood Agentic");
  await page.getByRole("button",{name:"SAVE MCP INFORMATION"}).click();
  await expect(page.getByText("Non-secret MCP configuration saved.")).toBeVisible();
  await page.getByLabel("Official MCP endpoint").fill("https://example.com/mcp");
  await expect(page.getByRole("button",{name:"SAVE MCP INFORMATION"})).toBeDisabled();
});
