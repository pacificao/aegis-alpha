import{render,screen}from"@testing-library/react";import{describe,it,expect}from"vitest";import Header from"./Header";
describe("Header",()=>{it("renders platform page context",()=>{render(<Header title="Development Roadmap" subtitle="Twelve governed phases"/>);expect(screen.getByText("Development Roadmap")).toBeInTheDocument()})});
