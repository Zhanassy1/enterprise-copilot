import { InviteAcceptance } from "@/components/invite/invite-acceptance";

type Props = { params: Promise<{ token: string }> };

export default async function InviteTokenPage({ params }: Props) {
  const { token } = await params;
  return <InviteAcceptance token={token} />;
}
