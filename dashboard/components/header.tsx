"use client";
import { useScroll } from "@/hooks/use-scroll";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MobileNav } from "@/components/mobile-nav";
import { useRouter } from "next/navigation";

export const navLinks = [];

export function Header() {
	const router 	= useRouter()
	const scrolled = useScroll(10);

	return (
		<header
			className={cn("sticky top-0 z-50 w-full border-transparent border-b", {
				"border-border bg-background/95 backdrop-blur-sm supports-backdrop-filter:bg-background/50":
					scrolled,
			})}
		>
			<nav className="flex h-14  items-center justify-between px-4">
				<div className="rounded-md p-2">
					<div className="relative w-25 md:w-35 lg:w-40  aspect-video cursor-pointer">
						<Image src={'/ackermans_logo.svg'} alt="logo" fill/>
					</div>
				</div>
				<div className="hidden items-center gap-3 md:flex">
					<Button variant={'outline'} className="cursor-pointer text-primary font-semibold px-12 rounded-sm" onClick={()=>{
						router.push('/login')
					}}>Sign In</Button>
					<Button variant={'ghost'} className="cursor-pointer text-primary font-semibold px-12 rounded-sm">Get Started</Button>
				</div>
				<MobileNav />
			</nav>
		</header>
	);
}
