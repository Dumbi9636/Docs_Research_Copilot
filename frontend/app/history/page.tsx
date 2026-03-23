import { redirect } from "next/navigation";

// /history 는 /mypage 로 통합되었습니다.
export default function HistoryPage() {
  redirect("/mypage");
}
