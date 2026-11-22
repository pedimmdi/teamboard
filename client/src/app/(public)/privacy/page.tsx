import { LegalDocument, legalMetadata } from "@/components/website/legal-document";

export function generateMetadata() {
  return legalMetadata("privacy");
}

export default function Privacy() {
  return <LegalDocument page="privacy" />;
}
