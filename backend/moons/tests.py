from app.test import TestCase
from .parser import process_moon_paste
from .models import EveMoon, EveMoonDistribution

paste = """
Moon	Moon Product	Quantity	Ore TypeID	SolarSystemID	PlanetID	MoonID
Rahadalon V - Moon 2						
	Bitumens	0.5413627028	45492	30002982	40189228	40189231
	Sylvite	0.2586372793	45491	30002982	40189228	40189231
Rahadalon VI - Moon 1						
	Bitumens	0.2821700573	45492	30002982	40189232	40189233
	Cobaltite	0.08585818857	45494	30002982	40189232	40189233
	Sylvite	0.2980297208	45491	30002982	40189232	40189233
	Vanadinite	0.3339420557	45500	30002982	40189232	40189233
Rahadalon VI - Moon 4						
	Chromite	0.2833463252	45501	30002982	40189232	40189236
	Sylvite	0.175055027	45491	30002982	40189232	40189236
	Zeolites	0.34159863	45490	30002982	40189232	40189236
Rahadalon VII - Moon 7						
	Bitumens	0.5342812538	45492	30002982	40189237	40189244
	Coesite	0.2657187581	45493	30002982	40189237	40189244
Rahadalon VIII - Moon 1						
	Bitumens	0.5284282565	45492	30002982	40189245	40189246
	Sylvite	0.2715717256	45491	30002982	40189245	40189246
"""


# Create your tests here.
class EveMoonPasteTestCase(TestCase):
    """Test case for the moon paste parser."""

    def test_process_moon_paste(self):
        process_moon_paste(paste)
        self.assertEqual(EveMoon.objects.count(), 5)
        self.assertEqual(EveMoonDistribution.objects.count(), 13)
        self.assertEqual(
            EveMoonDistribution.objects.filter(ore="Bitumens").count(), 4
        )

