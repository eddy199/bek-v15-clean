import tkinter as tk
import random
import unittest
import sys


class SnakeGame:
    """Jeu 2D de type Snake utilisant tkinter et l'architecture BEK."""

    def __init__(self, master, largeur_jeu=600, hauteur_jeu=400, taille_case=20):
        """Initialise le jeu, l'interface graphique et les variables d'état."""
        self.master = master
        self.largeur_jeu = largeur_jeu
        self.hauteur_jeu = hauteur_jeu
        self.taille_case = taille_case

        self.master.title("Jeu 2D - Snake BEK")
        self.master.resizable(False, False)

        self.canvas = tk.Canvas(
            self.master,
            width=self.largeur_jeu,
            height=self.hauteur_jeu,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.score = 0
        self.vitesse = 150
        self.direction = "droite"
        self.prochaine_direction = "droite"
        self.serpent = []
        self.nourriture = None
        self.en_cours = False

        self.master.bind("<KeyPress>", self.handle_keypress)

        self.initialiser_partie()

    def initialiser_partie(self):
        """Réinitialise les variables de jeu pour démarrer une nouvelle partie."""
        try:
            self.score = 0
            self.direction = "droite"
            self.prochaine_direction = "droite"
            self.en_cours = True

            position_x_initiale = 100
            position_y_initiale = 100
            self.serpent = [
                (position_x_initiale, position_y_initiale),
                (
                    position_x_initiale - self.taille_case,
                    position_y_initiale,
                ),
                (
                    position_x_initiale - 2 * self.taille_case,
                    position_y_initiale,
                ),
            ]

            self.generer_nourriture()
            self.afficher_score()
            self.boucle_jeu()
        except Exception as erreur:
            print(f"Erreur lors de l'initialisation de la partie : {erreur}")

    def generer_nourriture(self):
        """Place la nourriture à une position aléatoire non occupée par le serpent."""
        while True:
            x = random.randint(
                0, (self.largeur_jeu // self.taille_case) - 1
            ) * self.taille_case
            y = random.randint(
                0, (self.hauteur_jeu // self.taille_case) - 1
            ) * self.taille_case
            if (x, y) not in self.serpent:
                self.nourriture = (x, y)
                break

    def afficher_score(self):
        """Met à jour l'affichage du score courant sur le canvas."""
        self.canvas.delete("score")
        self.canvas.create_text(
            50,
            20,
            text=f"Score: {self.score}",
            fill="white",
            font=("Arial", 16, "bold"),
            tag="score",
        )

    def handle_keypress(self, event):
        """Gère les entrées clavier pour changer la direction du serpent."""
        touche = event.keysym.lower()

        correspondances = {
            "up": "haut",
            "down": "bas",
            "left": "gauche",
            "right": "droite",
            "z": "haut",
            "s": "bas",
            "q": "gauche",
            "d": "droite",
            "w": "haut",
            "a": "gauche",
        }

        nouvelle_direction = correspondances.get(touche)

        if nouvelle_direction is None:
            return

        opposes = {
            "haut": "bas",
            "bas": "haut",
            "gauche": "droite",
            "droite": "gauche",
        }

        if opposes.get(nouvelle_direction) != self.direction:
            self.prochaine_direction = nouvelle_direction

    def deplacer_serpent(self):
        """Calcule la nouvelle position du serpent selon la direction actuelle."""
        self.direction = self.prochaine_direction

        tete_x, tete_y = self.serpent[0]

        deplacements = {
            "haut": (0, -self.taille_case),
            "bas": (0, self.taille_case),
            "gauche": (-self.taille_case, 0),
            "droite": (self.taille_case, 0),
        }

        delta_x, delta_y = deplacements[self.direction]
        nouvelle_tete = (tete_x + delta_x, tete_y + delta_y)

        self.serpent.insert(0, nouvelle_tete)

        if nouvelle_tete == self.nourriture:
            self.score += 10
            self.afficher_score()
            self.generer_nourriture()
            if self.vitesse > 50:
                self.vitesse -= 5
        else:
            self.serpent.pop()

    def verifier_collisions(self):
        """Vérifie les collisions avec les murs et le corps du serpent."""
        tete_x, tete_y = self.serpent[0]

        if (
            tete_x < 0
            or tete_x >= self.largeur_jeu
            or tete_y < 0
            or tete_y >= self.hauteur_jeu
        ):
            return True

        if self.serpent[0] in self.serpent[1:]:
            return True

        return False

    def dessiner(self):
        """Dessine tous les éléments du jeu sur le canvas."""
        self.canvas.delete("all")

        self.afficher_score()

        if self.nourriture:
            nourriture_x, nourriture_y = self.nourriture
            self.canvas.create_rectangle(
                nourriture_x,
                nourriture_y,
                nourriture_x + self.taille_case,
                nourriture_y + self.taille_case,
                fill="red",
                outline="darkred",
                tag="nourriture",
            )

        for index, (segment_x, segment_y) in enumerate(self.serpent):
            couleur = "lime" if index == 0 else "green"
            self.canvas.create_rectangle(
                segment_x,
                segment_y,
                segment_x + self.taille_case,
                segment_y + self.taille_case,
                fill=couleur,
                outline="darkgreen",
                tag="serpent",
            )

    def afficher_game_over(self):
        """Affiche l'écran de fin de partie avec le score final."""
        self.canvas.create_text(
            self.largeur_jeu // 2,
            self.hauteur_jeu // 2 - 20,
            text="GAME OVER",
            fill="white",
            font=("Arial", 30, "bold"),
            tag="game_over",
        )
        self.canvas.create_text(
            self.largeur_jeu // 2,
            self.hauteur_jeu // 2 + 20,
            text=f"Score final: {self.score}",
            fill="white",
            font=("Arial", 16),
            tag="game_over",
        )
        self.canvas.create_text(
            self.largeur_jeu // 2,
            self.hauteur_jeu // 2 + 60,
            text="Appuyez sur ESPACE pour rejouer",
            fill="gray",
            font=("Arial", 12),
            tag="game_over",
        )

    def boucle_jeu(self):
        """Boucle principale gérant le timing, les mises à jour et le rendu."""
        if not self.en_cours:
            self.afficher_game_over()
            return

        try:
            self.deplacer_serpent()

            if self.verifier_collisions():
                self.en_cours = False
                self.dessiner()
                self.afficher_game_over()
                return

            self.dessiner()
            self.master.after(self.vitesse, self.boucle_jeu)
        except Exception as erreur:
            print(f"Erreur dans la boucle de jeu : {erreur}")
            self.en_cours = False


class TestSnakeGame(unittest.TestCase):
    """Tests unitaires pour la logique métier du jeu Snake."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.game = SnakeGame(self.root, largeur_jeu=400, hauteur_jeu=300, taille_case=20)

    def tearDown(self):
        self.root.destroy()

    def test_initialisation_serpent(self):
        """Le serpent doit être initialisé avec trois segments."""
        self.assertEqual(len(self.game.serpent), 3)

    def test_deplacement_vers_la_droite(self):
        """Le déplacement vers la droite doit augmenter l'abscisse de la tête."""
        self.game.direction = "droite"
        self.game.prochaine_direction = "droite"
        tete_avant = self.game.serpent[0]
        self.game.deplacer_serpent()
        tete_apres = self.game.serpent[0]
        self.assertEqual(tete_apres[0], tete_avant[0] + self.game.taille_case)
        self.assertEqual(tete_apres[1], tete_avant[1])

    def test_collision_mur_gauche(self):
        """Une tête en position x=0 se déplaçant vers la gauche doit coller le mur."""
        self.game.serpent = [(0, 0), (20, 0), (40, 0)]
        self.game.direction = "gauche"
        self.game.prochaine_direction = "gauche"
        self.game.deplacer_serpent()
        self.assertTrue(self.game.verifier_collisions())

    def test_collision_avec_le_corps(self):
        """Une tête occupant une case déjà prise par le corps est une collision."""
        self.game.serpent = [(100, 100), (80, 100), (100, 100)]
        self.assertTrue(self.game.verifier_collisions())

    def test_manger_nourriture_allonge_le_serpent(self):
        """Manger la nourriture doit augmenter la taille du serpent d'un segment."""
        taille_avant = len(self.game.serpent)
        self.game.serpent[0] = self.game.nourriture
        self.game.deplacer_serpent()
        self.assertEqual(len(self.game.serpent), taille_avant + 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main(argv=["first-arg"], exit=False)
    else:
        root = tk.Tk()
        jeu = SnakeGame(root)
        root.mainloop()