"use client";
import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {Activity,BookOpen,ChartNoAxesCombined,ChevronDown,Landmark,Lightbulb,LogOut,Server} from "lucide-react";
import {api} from "@/lib/api";

const groups=[
  {label:"Portfolio",icon:Landmark,items:[
    ["/portfolio","Overview"],
    ["/risk","Risk controls"],
  ]},
  {label:"Scenarios",icon:BookOpen,items:[
    ["/strategies","Library & parameters"],
  ]},
  {label:"Performance",icon:ChartNoAxesCombined,items:[
    ["/performance","Analytics overview"],
    ["/lab","Aegis Lab"],
    ["/simulator","Aegis Simulator"],
  ]},
  {label:"Suggested Adjustments",icon:Lightbulb,items:[
    ["/adjustments","Suggestions & notes"],
    ["/intelligence","Aegis Intelligence"],
  ]},
  {label:"System",icon:Server,items:[
    ["/system","System status"],
    ["/activity","Activity log"],
    ["/data","Data sources"],
    ["/roadmap","Development roadmap"],
    ["/security","Security"],
    ["/settings","Settings"],
  ]},
] as const;
export default function AppShell({children}:{children:React.ReactNode}){
  const path=usePathname();const router=useRouter();
  async function logout(){const me=await api<{csrf_token:string}>("/api/auth/me");await api("/api/auth/logout",{method:"POST",headers:{"X-CSRF-Token":me.csrf_token}});router.push("/login")}
  return <div className="shell"><aside className="sidebar">
    <div className="brand"><div className="mark">A</div><div><h1>AEGIS ALPHA</h1><span>Quantitative systems</span></div></div>
    <nav className="nav grouped-nav">
      <Link href="/" className={path==="/"?"active nav-dashboard":"nav-dashboard"}><Activity size={15}/>Dashboard</Link>
      {groups.map(group=>{const active=group.items.some(([href])=>path===href);const Icon=group.icon;return <details key={group.label} className="nav-group" open={active||undefined}>
        <summary className={active?"group-active":""}><Icon size={15}/><span>{group.label}</span><ChevronDown className="chevron" size={14}/></summary>
        <div className="subnav">{group.items.map(([href,label])=><Link key={href} href={href} className={path===href?"active":""}>{label}</Link>)}</div>
      </details>})}
    </nav>
    <div className="rail-status">EXECUTION LAYER<br/><span className="disabled">● TRADING DISABLED</span></div>
  </aside><main className="content"><div className="topbar"><div className="eyebrow">Private operator console · Phase 08 in progress</div><button className="logout" onClick={logout}><LogOut size={13}/> Logout</button></div>{children}</main></div>
}

