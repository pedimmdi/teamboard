import Link from "next/link";
import McpUrlCopy from "@/components/website/mcp-url-copy";
import { WebsiteIcon } from "@/components/website/website-icons";
import { getLocale } from "@/lib/server-preferences";
import { getMcpPublicUrl, mcpPageCopy, mcpProviders } from "@/lib/mcp-public";
import { publicMetadata, websitePath } from "@/lib/website";
import styles from "../website.module.css";

const localGuide = "https://github.com/pedimmdi/teamboard/blob/main/docs/mcp-local.md";

export async function generateMetadata() {
  const locale = await getLocale();
  const copy = mcpPageCopy[locale];
  return publicMetadata(copy.title, copy.description, "/mcp", locale);
}

export default async function McpPage() {
  const locale = await getLocale();
  const copy = mcpPageCopy[locale];
  const url = getMcpPublicUrl(process.env.TEAMBOARD_MCP_PUBLIC_URL);
  return (
    <article>
      <header className={styles.masthead}>
        <div>
          <h1>{copy.title}</h1>
          <p>{copy.lead}</p>
          <div className={styles.mcpActions}>
            <Link className={styles.primary} href="#setup">{copy.seeSetup}</Link>
            <Link className={styles.secondary} href={localGuide}>{copy.developerGuide}</Link>
          </div>
        </div>
      </header>

      <div className={styles.section}>
        <section className={styles.mcpCard} aria-labelledby="mcp-address">
          <h2 id="mcp-address">{url ? copy.serverUrl : copy.preview}</h2>
          <p>{url ? copy.endpointDescription : copy.previewDescription}</p>
          {url && <McpUrlCopy url={url} labels={copy.copy} />}
          <p>{copy.unverified}</p>
        </section>

        <section className={styles.mcpGroup} aria-labelledby="mcp-prompts">
          <h2 id="mcp-prompts">{copy.promptsTitle}</h2>
          <p>{copy.promptsDescription}</p>
          <div className={styles.mcpGrid}>
            {copy.prompts.map(({ question, caption, icon }) => (
              <div className={styles.mcpCard} key={caption}>
                <span className={styles.featureIcon}><WebsiteIcon name={icon} /></span>
                <h3>{caption}</h3>
                <p>{question}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.mcpGroup} aria-labelledby="setup">
          <h2 id="setup">{copy.setupTitle}</h2>
          <p>{copy.setupDescription}</p>
          <div className={styles.mcpGrid}>
            {mcpProviders.map(({ id, name, docs }) => (
              <section className={styles.mcpCard} key={id}>
                <h3><bdi>{name}</bdi></h3>
                <p>{copy.providers[id].availability}</p>
                <ol>{copy.providers[id].steps.map((step) => <li key={step}>{step}</li>)}</ol>
                <Link href={docs}>{copy.providerGuide(name)}</Link>
              </section>
            ))}
          </div>
        </section>

        <div className={styles.mcpGrid}>
          <section className={styles.mcpCard}>
            <h2>{copy.securityTitle}</h2>
            <p>{copy.security}</p>
            <Link href={websitePath("/privacy", locale)}>{copy.privacy}</Link>
          </section>
          <section className={styles.mcpCard}>
            <h2>{copy.disconnectTitle}</h2>
            <p>{copy.disconnect}</p>
            <Link href={websitePath("/contact", locale)}>{copy.contact}</Link>
          </section>
        </div>

        <section className={styles.mcpGroup} aria-labelledby="mcp-faq">
          <h2 id="mcp-faq">{copy.faqTitle}</h2>
          {copy.faq.map(({ question, answer }) => (
            <details className={styles.mcpCard} key={question}>
              <summary>{question}</summary>
              <p>{answer}</p>
            </details>
          ))}
          <div className={styles.mcpActions}>
            <Link href="https://aistudio.google.com/docs/function-calling#mcp">{copy.sdkGuide}</Link>
            <Link href="https://geminicli.com/docs/tools/mcp-server/">{copy.cliGuide}</Link>
          </div>
        </section>
      </div>
    </article>
  );
}
