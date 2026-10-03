import {expect, test} from '@playwright/test';

test('completes the private forecasting core workflow', async ({page}) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.E2E_EMAIL ?? 'owner@example.com');
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD ?? 'correct horse battery staple');
  await page.getByRole('button', {name: 'Sign in'}).click();

  await expect(page).toHaveURL(/\/competitions$/);
  await page.reload();
  await expect(page.getByRole('heading', {name: 'Competitions'})).toBeVisible();
  const competitionName = `Browser Cup ${Date.now()}`;
  await page.getByLabel('Competition name').fill(competitionName);
  await page.getByRole('button', {name: 'Create competition'}).click();
  await page.reload();
  await expect(page.getByRole('heading', {name: competitionName, exact: true})).toBeVisible();

  const apiBase = 'http://127.0.0.1:8000';
  const competition = await page.request.get(`${apiBase}/competitions`);
  const competitions = await competition.json();
  const ownedCompetition = competitions.find((item: {name: string}) => item.name === competitionName);
  if (!ownedCompetition) throw new Error('Created competition was not returned');
  const question = await page.request.post(`${apiBase}/competitions/${ownedCompetition.id}/questions`, {
    data: {title: 'Will the browser workflow complete?'},
  });
  expect(question.ok()).toBeTruthy();
  const questionData = await question.json();
  await page.goto(`/questions/${questionData.id}`);

  await expect(page.getByRole('heading', {name: 'Will the browser workflow complete?'})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Monitoring'})).toBeVisible();
  await expect(page.getByText('Monitoring is disabled')).toBeVisible();
  await page.getByRole('button', {name: 'Enable monitoring'}).click();
  await expect(page.getByText('Monitoring is enabled')).toBeVisible();
  await page.getByRole('button', {name: 'Monitor now'}).click();
  await expect(page.getByText('Monitoring is enabled')).toBeVisible();
  await page.getByLabel('Human probability (%)').fill('64');
  await page.getByLabel('Rationale (optional)').fill('Initial browser-tested estimate.');
  await page.getByRole('button', {name: 'Save human forecast'}).click();
  await expect(page.getByText('Initial browser-tested estimate.')).toBeVisible();

  await page.getByLabel('Research title').fill('Official release');
  await page.getByLabel('Research summary').fill('The official release supports the estimate.');
  await page.getByLabel('Source URL').fill('https://example.org/release');
  await page.getByLabel('Source name').fill('Official source');
  await page.getByRole('button', {name: 'Add candidate'}).click();
  await expect(page.getByText('Official release')).toBeVisible();
  await page.getByRole('button', {name: 'Approve Evidence'}).click();
  await expect(page.getByText('Status: approved')).toBeVisible();

  await page.getByLabel('Model rationale').fill('A transparent base-rate model.');
  await page.getByRole('button', {name: 'Create Draft Model'}).click();
  await expect(page.getByText('Draft model')).toBeVisible();
  await page.getByRole('button', {name: 'Approve Model'}).click();
  await expect(page.getByText('Approved model')).toBeVisible();
  await page.getByRole('button', {name: 'Run Model'}).click();
  await page.reload();
  await expect(page.getByRole('heading', {name: 'Analysis / Visuals'})).toBeVisible();
  await expect(page.getByText('Probability History')).toBeVisible();

  await expect(page.getByRole('heading', {name: 'Copilot'})).toBeVisible();
  await expect(page.getByText(/Copilot cannot change forecasts or evidence/)).toBeVisible();
  await page.getByLabel('Copilot message').fill('Which model should I use?');
  await page.getByRole('button', {name: 'Send message'}).click();
  await expect(page.getByText('Copilot is unavailable. Try again.', {exact: true})).toBeVisible();

  await page.getByRole('button', {name: 'Load decision history'}).click();
  await page.getByLabel('Decision rationale').fill('Final decision after reviewing evidence and model.');
  await page.getByRole('button', {name: 'Record decision'}).click();
  await expect(page.getByText('Final decision after reviewing evidence and model.')).toBeVisible();
  await page.reload();
  await page.getByRole('button', {name: 'Load decision history'}).click();
  await expect(page.getByRole('heading', {name: 'Activity history'})).toBeVisible();
  await expect(page.getByText('decision_recorded')).toBeVisible();

  await page.goto('/competitions');
  await expect(page.getByRole('heading', {name: 'Attention priorities'})).toBeVisible();
  await expect(page.locator(`a[href="/questions/${questionData.id}"]`)).toHaveText(
    'Will the browser workflow complete?',
  );

  await page.goto('/attention');
  await expect(page.getByRole('heading', {name: 'Notifications'})).toBeVisible();
  for (const label of ['Enable delivery', 'Deliver alerts', 'Deliver digests']) {
    const control = page.getByLabel(label);
    if (!await control.isChecked()) await control.click();
    await expect(control).toBeChecked();
  }
  await expect(page.getByLabel('Enable delivery')).toBeChecked();
  await expect(page.getByLabel('Deliver alerts')).toBeChecked();
  await expect(page.getByLabel('Deliver digests')).toBeChecked();

  await page.getByRole('button', {name: 'Sign out'}).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(async () => (
    await fetch('http://127.0.0.1:8000/auth/me', {credentials: 'include'})
  ).status)).toBe(401);
});
