import "./globals.css";import type {Metadata} from "next";
export const metadata:Metadata={title:"Aegis Alpha",description:"Private quantitative investment development platform"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}

