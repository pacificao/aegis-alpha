"use client";
import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {Activity,BookOpen,Landmark,LogOut,Map,ScrollText,Server,Settings,Shield} from "lucide-react";
import {api} from "@/lib/api";
const links=[
  ["/","Dashboard",Activity],
  ["/portfolio","Portfolio",Landmark],
  ["/strategies","Strategies",BookOpen],
  ["/activity","Activity",ScrollText],
  ["/roadmap","Roadmap",Map],
  ["/security","Security",Shield],
  ["/settings","Settings",Settings],
  ["/system","System",Server],
] as const;
export default function AppShell({children}:{children:React.ReactNode}){
  const path=usePathname();const router=useRouter();
  async function logout(){const me=await api<{csrf_token:string}>("/api/auth/me");await api("/api/auth/logout",{method:"POST",headers:{"X-CSRF-Token":me.csrf_token}});router.push("/login")}
  return <div className="shell"><aside className="sidebar">
    <div className="brand"><div className="mark">A</div><div><h1>AEGIS ALPHA</h1><span>Quantitative systems</span></div></div>
    <nav className="nav">{links.map(([href,label,Icon])=><Link key={href} href={href} className={path===href?"active":""}><Icon size={15}/>{label}</Link>)}</nav>
    <div className="rail-status">EXECUTION LAYER<br/><span className="disabled">● TRADING DISABLED</span></div>
  </aside><main className="content"><div className="topbar"><div className="eyebrow">Private operator console · Phase 02</div><button className="logout" onClick={logout}><LogOut size={13}/> Logout</button></div>{children}</main></div>
}

