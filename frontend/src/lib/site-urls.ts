const repo = (
  process.env.NEXT_PUBLIC_GITHUB_REPO ?? "Zhanassy1/enterprise-copilot"
).replace(/^\/+|\/+$/g, "");

const repoRoot = `https://github.com/${repo}`;

export const siteUrls = {
  githubRepo: repoRoot,
  githubDocs: `${repoRoot}/tree/main/docs`,
  githubReadme: `${repoRoot}/blob/main/README.md`,
  /** Якоря заданы в README.md (<a id="...">) для стабильных ссылок с главной репозитория. */
  evaluatorGuide: `${repoRoot}#evaluator-five-minutes`,
  demoQuick1Min: `${repoRoot}#demo-quick-1min`,
  demoScreenshots: `${repoRoot}#screenshots`,
  productFlow: `${repoRoot}#product-flow`,
  githubGlossary: `${repoRoot}/blob/main/docs/product-glossary.md`,
  githubQuotas: `${repoRoot}/blob/main/docs/quotas.md`,
  demoMedia: `${repoRoot}/blob/main/docs/DEMO_MEDIA.md`,
} as const;
