import { test, expect } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const resetStudent2 = async () => {
  await execAsync(
    'C:\\Users\\Code\\Desktop\\DoubtDesk\\v1\\backend\\.venv\\Scripts\\python.exe C:\\Users\\Code\\Desktop\\DoubtDesk\\v1\\backend\\scripts\\reset_student2_assignment.py'
  );
};

test.describe('Slice A Reproduction: Student Baseline Submission & Next Action', () => {
  test('submitting baseline should immediately show Read study guide next action on result and list', async ({ page }) => {
    await resetStudent2();
    // 1. Log in as student2
    await page.goto('/login');
    await page.locator('input[type="text"]').fill('student2@outr.ac.in');
    await page.locator('input[type="password"]').fill('StudentPass123!');
    await page.locator('button[type="submit"]').click();

    await page.waitForURL('**/doubts');

    // 2. Navigate to /quiz tab
    await page.goto('/quiz');
    await expect(page.locator('h3:has-text("Targeted Learning Support")')).toBeVisible({ timeout: 10000 });

    // 3. Find the assigned intervention card and click Start/Resume Baseline
    const startBaselineBtn = page.getByRole('article').getByRole('button', { name: /Start baseline|Resume baseline/i });
    await expect(startBaselineBtn).toBeVisible();
    await startBaselineBtn.click();

    // 4. In CBT mode, answer each question
    await expect(page.locator('button:has-text("Submit Quiz")')).toBeVisible({ timeout: 10000 });

    // Click the first available option button for each question card
    const questionCards = page.locator('[data-testid="quiz-question-item"]');
    const cardCount = await questionCards.count();
    for (let i = 0; i < cardCount; i++) {
      const card = questionCards.nth(i);
      const opt = card.locator('button').first();
      if (await opt.isVisible()) {
        await opt.click();
        await page.waitForTimeout(300);
      }
    }

    // 5. Submit Quiz
    const submitBtn = page.locator('button:has-text("Submit Quiz")');
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    // 6. Verification on Result Screen:
    await expect(page.locator('h3:has-text("Quiz Submitted")')).toBeVisible({ timeout: 10000 });

    // FAILING ASSERTION 1: The result screen must have a prominent next action button for the study guide
    const nextActionBtn = page.getByRole('button', { name: /Read study guide/i });
    await expect(nextActionBtn).toBeVisible({ timeout: 3000 });

    // 7. Click Back to Quizzes
    await page.locator('button:has-text("Back to Quizzes")').click();

    // Verification 2: Back on the quiz list, the intervention card MUST NOT show "Start baseline"
    await expect(page.getByRole('article').getByRole('button', { name: /Start baseline/i })).not.toBeVisible();
    // And it MUST show "Read study guide"
    await expect(page.getByRole('article').getByRole('button', { name: /Read study guide|Study guide/i })).toBeVisible();
  });
});
