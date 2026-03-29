const repo = (
  process.env.NEXT_PUBLIC_GITHUB_REPO ?? "Zhanassy1/enterprise-copilot"
).replace(/^\/+|\/+$/g, "");

export const siteUrls = {
  githubRepo: `https://github.com/${repo}`,
  githubDocs: `https://github.com/${repo}/tree/main/docs`,
  githubReadme: `https://github.com/${repo}/blob/main/README.md`,
} as const;
