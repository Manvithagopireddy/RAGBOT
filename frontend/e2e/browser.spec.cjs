const { test, expect } = require('@playwright/test');
const base = process.env.RAGBOT_BROWSER_URL || 'http://127.0.0.1:18080';

for (const viewport of [{width: 390, height: 844}, {width: 1440, height: 900}]) {
  test('register and sign in at ' + viewport.width, async ({ page }) => {
    await page.setViewportSize(viewport);
    const name = 'browser_' + Date.now() + '_' + viewport.width;
    const password = 'BrowserTestAa1!';
    await page.goto(base + '/register');
    await page.getByLabel('Username', {exact: true}).fill(name);
    await page.getByLabel('Email', {exact: true}).fill(name + '@example.com');
    await page.getByLabel('Password', {exact: true}).fill(password);
    await page.getByRole('button', {name: 'Create Account'}).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.getByLabel('Username or Email').fill(name);
    await page.getByLabel('Password', {exact: true}).fill(password);
    await page.getByRole('button', {name: 'Sign In'}).click();
    await expect(page.getByRole('textbox', {name: 'Chat message'})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    if (viewport.width < 768) {
      await page.getByRole('button', {name: 'Chats', exact: true}).click();
    }
    await page.getByRole('button', {name: 'New Chat'}).click();
    await expect(page.getByRole('textbox', {name: 'Chat message'})).toBeVisible();
  });
}
