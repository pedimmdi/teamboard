import Image from "next/image";

export default function DesignIcon({
  name,
}: {
  name: "folder" | "users" | "settings" | "chevron-right" | "chevrons-up-down";
}) {
  return (
    <Image
      src={`/icons/${name}.svg`}
      width={20}
      height={20}
      alt=""
      aria-hidden="true"
    />
  );
}
