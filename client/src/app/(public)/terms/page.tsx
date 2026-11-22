import { LegalDocument, legalMetadata } from "@/components/website/legal-document";

export function generateMetadata() {
  return legalMetadata("terms");
}

export default function Terms() {
  return <LegalDocument page="terms" />;
}
