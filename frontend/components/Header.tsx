export default function Header({title,subtitle}:{title:string;subtitle:string}){return <header style={{marginBottom:24}}><h2 style={{fontSize:28,margin:'0 0 6px'}}>{title}</h2><div className="sub">{subtitle}</div></header>}

