import { test, expect } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const resetStudent2 = async () => {
  await execAsync(
    'C:\\Users\\Code\\Desktop\\DoubtDesk\\v1\\backend\\.venv\\Scripts\\python.exe C:\\Users\\Code\\Desktop\\DoubtDesk\\v1\\backend\\scripts\\reset_student2_assignment.py'
  );
};

test.describe('Student Learning Support & Quiz Journey', () => {
  test.beforeEach(async ({ page }) => {
    await resetStudent2();
    // Log in as student2
    await page.goto('/login');
    await page.locator('input[type="text"]').fill('student2@outr.ac.in');
    await page.locator('input[type="password"]').fill('StudentPass123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/doubts');
  });

  test('specialized intervention assessments are excluded from ordinary student quiz cards', async ({ page }) => {
    await page.goto('/quiz');
    await expect(page.locator('h3:has-text("Targeted Learning Support")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h3:has-text("Course Assessments & Quizzes")')).toBeVisible();

    // Verify ordinary course quiz exists
    await expect(page.locator('h3:has-text("BCI Types and Applications Quiz")')).toBeVisible();

    // Verify that the intervention assessments do NOT appear as ordinary quiz cards
    const quizCards = page.locator('div.border.rounded-\\[16px\\].bg-white.p-5');
    const ordinaryTitles = await quizCards.locator('h3').allTextContents();
    for (const title of ordinaryTitles) {
      expect(title.toLowerCase()).not.toContain('baseline');
      expect(title.toLowerCase()).not.toContain('reassessment');
    }
  });

  test('sidebar displays authoritative learning progress and subject scoping', async ({ page }) => {
    await page.goto('/quiz');

    // Verify Learning Progress Sidebar sections
    await expect(page.locator('h4:has-text("Learning Topics")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h4:has-text("Teacher Practice Questions")')).toBeVisible();
    await expect(page.locator('h4:has-text("Targeted Learning Support")')).toBeVisible();
    await expect(page.locator('text=Continue Learning')).toBeVisible();

    // Verify subject scoping: switch to BCI subject
    const bciSubjectBtn = page.getByRole('button', { name: /Brain Computer Interface/i }).first();
    await bciSubjectBtn.click();
    await page.waitForTimeout(500);

    // Support card remains visible under BCI subject
    await expect(page.getByRole('article')).toBeVisible();
  });

  test('full end-to-end journey: baseline -> study guide -> acknowledge -> reassessment -> results comparison', async ({ page }) => {
    test.setTimeout(60000);
    await page.goto('/quiz');
    await expect(page.locator('h3:has-text("Targeted Learning Support")')).toBeVisible({ timeout: 10000 });

    const card = page.getByRole('article').first();
    const startBaselineBtn = card.getByRole('button', { name: /Start baseline|Resume baseline/i });
    await expect(startBaselineBtn).toBeVisible();
    await startBaselineBtn.click();

    // 1. In CBT mode for Phase A Baseline: Answer all questions
    await expect(page.locator('button:has-text("Submit Quiz")')).toBeVisible({ timeout: 10000 });
    const questionCards = page.locator('[data-testid="quiz-question-item"]');
    const count = await questionCards.count();
    for (let i = 0; i < count; i++) {
      const qCard = questionCards.nth(i);
      const opt = qCard.locator('button').first();
      if (await opt.isVisible()) {
        await opt.click();
        await page.waitForTimeout(200);
      }
    }

    // Submit Baseline
    const submitBtn = page.locator('button:has-text("Submit Quiz")');
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    // 2. Result Screen for Phase A: Authoritative continuation action "Read study guide"
    await expect(page.locator('h3:has-text("Quiz Submitted")')).toBeVisible({ timeout: 10000 });
    const readGuideBtn = page.locator('.bg-emerald-50').getByRole('button', { name: /Read study guide/i });
    await expect(readGuideBtn).toBeVisible();
    await readGuideBtn.click();

    // Now in StudentSupportWorkspace (Step: Study Guide)
    await expect(page.locator('h3:has-text("Study Guide & Worked Examples")')).toBeVisible({ timeout: 10000 });
    // Check safe primer content rendering
    await expect(page.locator('[data-testid="study-guide-content"]')).toBeVisible();

    // Acknowledge the study guide
    const acknowledgeBtn = page.getByRole('button', { name: /I've reviewed the study guide|I have reviewed/i });
    if (await acknowledgeBtn.isVisible()) {
      await acknowledgeBtn.click();
      await page.waitForTimeout(800);
    }

    // Step 3 unlocked: Reassessment Ready Banner should now offer "Start Reassessment"
    const startReassessmentBtn = page.locator('.border-blue-200.bg-\\[\\#EAF5FF\\]').getByRole('button');
    await expect(startReassessmentBtn).toBeVisible({ timeout: 5000 });
    await startReassessmentBtn.click();

    // In CBT mode for Phase C Reassessment
    await expect(page.locator('button:has-text("Submit Quiz")')).toBeVisible({ timeout: 10000 });
    const cQuestions = page.locator('[data-testid="quiz-question-item"]');
    const cCount = await cQuestions.count();
    for (let i = 0; i < cCount; i++) {
      const qCard = cQuestions.nth(i);
      const opt = qCard.locator('button').first();
      if (await opt.isVisible()) {
        await opt.click();
        await page.waitForTimeout(200);
      }
    }

    // Submit reassessment
    const submitReassessBtn = page.locator('button:has-text("Submit Quiz")');
    await expect(submitReassessBtn).toBeEnabled({ timeout: 5000 });
    await submitReassessBtn.click();

    await page.waitForTimeout(1000);

    // Result screen should now show authoritative continuation action: "View results"
    await expect(page.locator('h3:has-text("Quiz Submitted")')).toBeVisible({ timeout: 10000 });
    const viewResultsBtn = page.locator('.bg-emerald-50').getByRole('button', { name: /View results/i });
    await expect(viewResultsBtn).toBeVisible();
    await viewResultsBtn.click();

    // Workspace Results Screen: Pre/Post comparison
    await expect(page.locator('h3:has-text("Support Journey Completed")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Baseline Score')).toBeVisible();
    await expect(page.locator('text=Reassessment Score')).toBeVisible();
    await expect(page.locator('text=Does not constitute causal evidence')).toBeVisible();

    // Return to quizzes list
    await page.getByRole('button', { name: /Return to Quizzes|Back to Quizzes/i }).first().click();

    // Verify completed support section is rendered
    await expect(page.locator('button:has-text("Completed Support")')).toBeVisible({ timeout: 5000 });
  });
});
